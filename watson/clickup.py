"""ClickUp time-tracking integration for Watson.

Pure helpers and a thin API client. `requests` is imported lazily at call
sites to match the cold-start concern Watson has with its crick sync
(see watson/watson.py `#312` comment).
"""

import re

import arrow

from .watson import WatsonError

CU_TAG_PREFIX = 'cu:'

CLICKUP_API_ROOT = 'https://api.clickup.com/api/v2'


def extract_clickup_id(frame):
    """Return the ClickUp task id embedded in `frame.tags`, or None.

    The id is stored as a tag of the form ``cu:<task_id>``. If more than one
    such tag is present, the first wins.
    """
    for tag in frame.tags:
        if tag.startswith(CU_TAG_PREFIX):
            return tag[len(CU_TAG_PREFIX):]
    return None


def non_cu_tags(frame):
    """Return the frame's tags with any ``cu:*`` entries removed."""
    return [t for t in frame.tags if not t.startswith(CU_TAG_PREFIX)]


_RELATIVE_DAY_RE = re.compile(r'^-(\d+)d$')


def parse_day(value):
    """Resolve a `--day` argument to a ``(start, stop)`` arrow pair.

    Accepts ``today``, ``yesterday``, ``-Nd`` (N days ago), or ``YYYY-MM-DD``.
    The returned span runs from local-midnight of the chosen day to
    local-midnight of the next day.
    """
    lowered = value.strip().lower()

    if lowered == 'today':
        offset = 0
    elif lowered == 'yesterday':
        offset = -1
    else:
        match = _RELATIVE_DAY_RE.match(lowered)
        if match:
            offset = -int(match.group(1))
        else:
            try:
                day = arrow.get(value, 'YYYY-MM-DD')
            except (ValueError, TypeError) as exc:
                raise WatsonError(
                    "Invalid --day value {!r}: use today, yesterday, -Nd, "
                    "or YYYY-MM-DD.".format(value)
                ) from exc
            start = arrow.Arrow(day.year, day.month, day.day).floor('day')
            return start, start.shift(days=1)

    start = arrow.now().shift(days=offset).floor('day')
    return start, start.shift(days=1)


class ClickUpClient:
    """Minimal ClickUp API client (creates time entries)."""

    def __init__(self, token, team_id):
        if not token or not team_id:
            raise WatsonError(
                "Missing ClickUp credentials. Set them with:\n"
                "    watson config clickup.token <your-token>\n"
                "    watson config clickup.team_id <your-team-id>"
            )
        self.token = token
        self.team_id = str(team_id)

    def _headers(self):
        return {
            'Authorization': self.token,
            'Content-Type': 'application/json',
        }

    def _time_entries_url(self):
        return '{}/team/{}/time_entries'.format(
            CLICKUP_API_ROOT, self.team_id,
        )

    def _tasks_url(self, list_id=None):
        if list_id:
            return '{}/list/{}/task'.format(CLICKUP_API_ROOT, list_id)
        return '{}/team/{}/task'.format(CLICKUP_API_ROOT, self.team_id)

    def search_tasks(self, substring, list_id=None,
                     include_closed=False, max_pages=10):
        """Return tasks whose name contains ``substring`` (case-insensitive).

        If ``list_id`` is given, the search is scoped to that list; otherwise
        it paginates the team-wide task endpoint. Stops paginating when a
        page returns fewer than 100 tasks or ``max_pages`` is reached.
        ClickUp's public v2 API has no server-side name filter, so matching
        is done client-side on each page.
        """
        import requests

        url = self._tasks_url(list_id)
        needle = substring.lower()
        results = []

        for page in range(max_pages):
            params = {
                'page': page,
                'subtasks': 'true',
                'include_closed': 'true' if include_closed else 'false',
            }
            try:
                response = requests.get(
                    url, params=params, headers=self._headers(),
                )
            except requests.ConnectionError as exc:
                raise WatsonError(
                    "Unable to reach the ClickUp API: {}".format(exc)
                )

            if response.status_code != 200:
                raise WatsonError(
                    "ClickUp API rejected task query (status {}): {}".format(
                        response.status_code, response.text,
                    )
                )

            tasks = response.json().get('tasks') or []
            for task in tasks:
                if needle in (task.get('name') or '').lower():
                    results.append(task)

            if len(tasks) < 100:
                break

        return results

    def create_time_entry(self, task_id, start, duration_ms,
                          description='', tags=None):
        """POST a time entry. Returns the newly created ClickUp entry id."""
        import requests

        payload = {
            'tid': task_id,
            'start': start.to('utc').int_timestamp * 1000,
            'duration': int(duration_ms),
            'description': description,
            'tags': [{'name': t} for t in (tags or [])],
        }

        try:
            response = requests.post(
                self._time_entries_url(),
                json=payload,
                headers=self._headers(),
            )
        except requests.ConnectionError as exc:
            raise WatsonError(
                "Unable to reach the ClickUp API: {}".format(exc)
            )

        if response.status_code not in (200, 201):
            raise WatsonError(
                "ClickUp API rejected time entry for task {} "
                "(status {}): {}".format(
                    task_id, response.status_code, response.text,
                )
            )

        body = response.json()
        data = body.get('data', body)
        entry_id = data.get('id') if isinstance(data, dict) else None
        if not entry_id:
            raise WatsonError(
                "ClickUp API did not return a time-entry id. Response: {}"
                .format(body)
            )
        return str(entry_id)
