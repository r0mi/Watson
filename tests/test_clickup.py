"""Tests for the ClickUp integration."""

from datetime import datetime

import arrow
import pytest

from watson import cli, clickup
from watson.cli import local_tz_info


# Fixed clock: 2026-04-20 14:30:00 local.
_FROZEN_NOW = datetime(2026, 4, 20, 14, 30, 0, tzinfo=local_tz_info())


@pytest.fixture
def frozen_now(mocker):
    mocker.patch('arrow.arrow.dt_datetime', wraps=datetime)
    arrow.arrow.dt_datetime.now.return_value = _FROZEN_NOW
    return _FROZEN_NOW


class _StubFrame:
    def __init__(self, tags, project='demo', id='f1'):
        self.tags = tags
        self.project = project
        self.id = id


def test_extract_clickup_id_first_cu_tag_wins():
    frame = _StubFrame(['bug', 'cu:ABC123', 'cu:ZZZZ'])
    assert clickup.extract_clickup_id(frame) == 'ABC123'


def test_extract_clickup_id_returns_none_when_absent():
    frame = _StubFrame(['bug', 'review'])
    assert clickup.extract_clickup_id(frame) is None


def test_non_cu_tags_strips_cu_prefix_tags():
    frame = _StubFrame(['cu:ABC', 'bug', 'cu:DEF', 'review'])
    assert clickup.non_cu_tags(frame) == ['bug', 'review']


@pytest.mark.parametrize('value,start_iso,stop_iso', [
    ('today', '2026-04-20', '2026-04-21'),
    ('TODAY', '2026-04-20', '2026-04-21'),
    ('yesterday', '2026-04-19', '2026-04-20'),
    ('-1d', '2026-04-19', '2026-04-20'),
    ('-3d', '2026-04-17', '2026-04-18'),
    ('2026-04-18', '2026-04-18', '2026-04-19'),
])
def test_parse_day(frozen_now, value, start_iso, stop_iso):
    start, stop = clickup.parse_day(value)
    assert start.format('YYYY-MM-DD') == start_iso
    assert stop.format('YYYY-MM-DD') == stop_iso
    assert start.hour == 0 and start.minute == 0 and start.second == 0


def test_parse_day_rejects_garbage(frozen_now):
    with pytest.raises(Exception):
        clickup.parse_day('next tuesday')


def _configure_clickup(watson_, token='T0K3N', team_id='42'):
    watson_.config.set('clickup', 'token', token)
    watson_.config.set('clickup', 'team_id', team_id)
    watson_.config = watson_.config  # mark changed
    watson_.save()


def _make_frame(watson_, project='demo', tags=None,
                start=None, stop=None):
    start = start or arrow.get('2026-04-20 09:00:00').replace(
        tzinfo=local_tz_info())
    stop = stop or start.shift(hours=1)
    return watson_.frames.add(project, start, stop, tags=tags or [])


def test_clickup_push_dry_run_lists_all_buckets(runner, watson, mocker,
                                                frozen_now):
    _configure_clickup(watson)
    post = mocker.patch('requests.post')
    with_id = _make_frame(watson, tags=['cu:TASK1'])
    _make_frame(watson, tags=['bug'],
                start=with_id.stop.shift(minutes=5))
    watson.save()

    result = runner.invoke(
        cli.clickup, ['push', '--day', 'today', '--dry-run'], obj=watson)
    assert result.exit_code == 0, result.output
    assert 'to push       : 1' in result.output
    assert 'missing id    : 1' in result.output
    assert 'TASK1' in result.output
    assert post.call_count == 0


def test_clickup_push_aborts_if_any_frame_missing_id(runner, watson, mocker,
                                                     frozen_now):
    _configure_clickup(watson)
    post = mocker.patch('requests.post')
    with_id = _make_frame(watson, tags=['cu:TASK1'])
    _make_frame(watson, tags=[], start=with_id.stop.shift(minutes=5))
    watson.save()

    result = runner.invoke(
        cli.clickup, ['push', '--day', 'today'], obj=watson)
    assert result.exit_code != 0, result.output
    assert 'missing a ClickUp id' in result.output
    assert post.call_count == 0


def test_clickup_push_force_skips_missing_id_frames(runner, watson, mocker,
                                                    frozen_now):
    _configure_clickup(watson)
    response = mocker.Mock()
    response.status_code = 200
    response.json.return_value = {'data': {'id': 'E1'}}
    post = mocker.patch('requests.post', return_value=response)

    with_id = _make_frame(watson, tags=['cu:TASK1'])
    without = _make_frame(watson, tags=['break'],
                          start=with_id.stop.shift(minutes=5))
    watson.save()

    result = runner.invoke(
        cli.clickup, ['push', '--day', 'today', '--force'], obj=watson)
    assert result.exit_code == 0, result.output
    assert post.call_count == 1
    # The missing-id frame is reported as skipped, not fatal.
    assert 'Skipping 1 frame' in result.output
    assert without.id[:7] in result.output
    # The tagged frame is pushed and recorded.
    assert watson.clickup_sync[with_id.id] == 'E1'
    assert without.id not in watson.clickup_sync


def test_clickup_push_creates_entries_and_records_sync_map(runner, watson,
                                                           mocker,
                                                           frozen_now):
    _configure_clickup(watson)
    response = mocker.Mock()
    response.status_code = 200
    response.json.return_value = {'data': {'id': 'CU_ENTRY_1'}}
    post = mocker.patch('requests.post', return_value=response)

    frame = _make_frame(watson, project='demo', tags=['cu:TASK1', 'bug'])
    watson.save()

    result = runner.invoke(
        cli.clickup, ['push', '--day', 'today'], obj=watson)
    assert result.exit_code == 0, result.output
    assert post.call_count == 1

    call = post.call_args
    payload = call.kwargs['json']
    assert payload['tid'] == 'TASK1'
    expected_ms = frame.start.to('utc').int_timestamp * 1000
    assert payload['start'] == expected_ms
    assert payload['duration'] == 3600 * 1000
    assert payload['description'] == 'demo [bug]'
    assert payload['tags'] == [{'name': 'bug'}]
    assert call.kwargs['headers']['Authorization'] == 'T0K3N'

    assert watson.clickup_sync[frame.id] == 'CU_ENTRY_1'


def test_clickup_push_skips_already_synced_frames(runner, watson, mocker,
                                                  frozen_now):
    _configure_clickup(watson)
    post = mocker.patch('requests.post')

    frame = _make_frame(watson, tags=['cu:TASK1'])
    watson.mark_clickup_synced(frame.id, 'PREVIOUS_ENTRY')
    watson.save()

    result = runner.invoke(
        cli.clickup, ['push', '--day', 'today'], obj=watson)
    assert result.exit_code == 0, result.output
    assert post.call_count == 0
    assert 'Nothing to push' in result.output


def test_clickup_push_force_repushes_already_synced(runner, watson, mocker,
                                                    frozen_now):
    _configure_clickup(watson)
    response = mocker.Mock()
    response.status_code = 200
    response.json.return_value = {'data': {'id': 'CU_ENTRY_2'}}
    post = mocker.patch('requests.post', return_value=response)

    frame = _make_frame(watson, tags=['cu:TASK1'])
    watson.mark_clickup_synced(frame.id, 'PREVIOUS_ENTRY')
    watson.save()

    result = runner.invoke(
        cli.clickup, ['push', '--day', 'today', '--force'], obj=watson)
    assert result.exit_code == 0, result.output
    assert post.call_count == 1
    assert watson.clickup_sync[frame.id] == 'CU_ENTRY_2'


def test_clickup_push_connection_error_surfaces(runner, watson, mocker,
                                                frozen_now):
    _configure_clickup(watson)
    import requests
    mocker.patch(
        'requests.post',
        side_effect=requests.ConnectionError('boom'),
    )
    _make_frame(watson, tags=['cu:TASK1'])
    watson.save()

    result = runner.invoke(
        cli.clickup, ['push', '--day', 'today'], obj=watson)
    assert result.exit_code != 0
    assert 'Unable to reach the ClickUp API' in result.output


def test_clickup_push_yesterday_selects_prior_days_frames(runner, watson,
                                                          mocker, frozen_now):
    _configure_clickup(watson)
    response = mocker.Mock()
    response.status_code = 200
    response.json.return_value = {'data': {'id': 'E1'}}
    post = mocker.patch('requests.post', return_value=response)

    y_start = arrow.get('2026-04-19 10:00:00').replace(tzinfo=local_tz_info())
    _make_frame(watson, tags=['cu:YTASK'], start=y_start,
                stop=y_start.shift(hours=2))
    _make_frame(watson, tags=['cu:TTASK'])
    watson.save()

    result = runner.invoke(
        cli.clickup, ['push', '--day', 'yesterday'], obj=watson)
    assert result.exit_code == 0, result.output
    assert post.call_count == 1
    assert post.call_args.kwargs['json']['tid'] == 'YTASK'


def test_start_cu_flag_adds_cu_tag(runner, watson):
    result = runner.invoke(
        cli.start, ['demo', '--cu', 'ABC123', '+bug'], obj=watson)
    assert result.exit_code == 0, result.output
    assert watson.current['tags'] == ['cu:ABC123', 'bug']


def test_clickup_tag_attaches_id(runner, watson):
    frame = _make_frame(watson, tags=['bug'])
    watson.save()

    result = runner.invoke(
        cli.clickup, ['tag', frame.id, 'ABC123'], obj=watson)
    assert result.exit_code == 0, result.output
    assert watson.frames[frame.id].tags == ['cu:ABC123', 'bug']


def test_clickup_tag_replaces_existing_cu_tag(runner, watson):
    frame = _make_frame(watson, tags=['cu:OLD', 'bug'])
    watson.save()

    result = runner.invoke(
        cli.clickup, ['tag', frame.id, 'NEW'], obj=watson)
    assert result.exit_code == 0, result.output
    assert watson.frames[frame.id].tags == ['cu:NEW', 'bug']


def test_clickup_tag_running_frame(runner, watson):
    runner.invoke(cli.start, ['demo', '+bug'], obj=watson)

    result = runner.invoke(cli.clickup, ['tag', 'TASK99'], obj=watson)
    assert result.exit_code == 0, result.output
    assert watson.current['tags'] == ['cu:TASK99', 'bug']


def test_clickup_tag_running_frame_replaces_existing_cu(runner, watson):
    runner.invoke(cli.start, ['demo', '+cu:OLD', '+bug'], obj=watson)

    result = runner.invoke(cli.clickup, ['tag', 'NEW'], obj=watson)
    assert result.exit_code == 0, result.output
    assert watson.current['tags'] == ['cu:NEW', 'bug']


def test_clickup_tag_no_args_no_running_frame_errors(runner, watson):
    result = runner.invoke(cli.clickup, ['tag', 'TASK99'], obj=watson)
    assert result.exit_code != 0
    assert 'No project started' in result.output


def test_clickup_push_missing_config_fails_gracefully(runner, watson, mocker,
                                                      frozen_now):
    # token+team_id never set
    post = mocker.patch('requests.post')
    _make_frame(watson, tags=['cu:TASK1'])
    watson.save()

    result = runner.invoke(
        cli.clickup, ['push', '--day', 'today'], obj=watson)
    assert result.exit_code != 0
    assert 'clickup.token' in result.output
    assert post.call_count == 0


def _mock_task(id, name, status='open', list_name='Dev',
               list_id='901234567890'):
    return {
        'id': id,
        'name': name,
        'status': {'status': status},
        'list': {'id': list_id, 'name': list_name},
    }


def test_clickup_find_returns_matches(runner, watson, mocker):
    _configure_clickup(watson)
    response = mocker.Mock()
    response.status_code = 200
    response.json.return_value = {'tasks': [
        _mock_task('1', 'Fix login bug'),
        _mock_task('2', 'Add dark mode'),
        _mock_task('3', 'Rework LOGIN session handling'),
    ]}
    get = mocker.patch('requests.get', return_value=response)

    result = runner.invoke(
        cli.clickup, ['find', 'login'], obj=watson)
    assert result.exit_code == 0, result.output
    assert '1' in result.output and 'Fix login bug' in result.output
    assert '3' in result.output and 'Rework LOGIN session handling' in \
        result.output
    assert 'Add dark mode' not in result.output
    # List id is printed so users can copy it into clickup.list_id config.
    assert 'list:901234567890' in result.output
    # Single page returned <100 tasks, so only one GET is made.
    assert get.call_count == 1


def test_clickup_find_paginates_until_short_page(runner, watson, mocker):
    _configure_clickup(watson)
    page1 = mocker.Mock()
    page1.status_code = 200
    page1.json.return_value = {'tasks': [
        _mock_task(str(i), 'task-{}'.format(i)) for i in range(100)
    ]}
    page2 = mocker.Mock()
    page2.status_code = 200
    page2.json.return_value = {'tasks': [
        _mock_task('needle', 'the match'),
    ]}
    get = mocker.patch('requests.get', side_effect=[page1, page2])

    result = runner.invoke(
        cli.clickup, ['find', 'match'], obj=watson)
    assert result.exit_code == 0, result.output
    assert 'the match' in result.output
    assert get.call_count == 2
    # Short second page stops pagination.
    assert get.call_args_list[0].kwargs['params']['page'] == 0
    assert get.call_args_list[1].kwargs['params']['page'] == 1


def test_clickup_find_scopes_to_list_id_from_config(runner, watson, mocker):
    _configure_clickup(watson)
    watson.config.set('clickup', 'list_id', '999')
    response = mocker.Mock()
    response.status_code = 200
    response.json.return_value = {'tasks': []}
    get = mocker.patch('requests.get', return_value=response)

    result = runner.invoke(cli.clickup, ['find', 'nothing'], obj=watson)
    assert result.exit_code == 0
    assert '/list/999/task' in get.call_args.args[0]


def test_clickup_find_override_list_id(runner, watson, mocker):
    _configure_clickup(watson)
    response = mocker.Mock()
    response.status_code = 200
    response.json.return_value = {'tasks': []}
    get = mocker.patch('requests.get', return_value=response)

    runner.invoke(
        cli.clickup, ['find', 'x', '--list-id', '777'], obj=watson)
    assert '/list/777/task' in get.call_args.args[0]


def test_clickup_find_limit_caps_output(runner, watson, mocker):
    _configure_clickup(watson)
    response = mocker.Mock()
    response.status_code = 200
    response.json.return_value = {'tasks': [
        _mock_task(str(i), 'match-{}'.format(i)) for i in range(5)
    ]}
    mocker.patch('requests.get', return_value=response)

    result = runner.invoke(
        cli.clickup, ['find', 'match', '--limit', '2'], obj=watson)
    assert result.exit_code == 0, result.output
    assert 'match-0' in result.output
    assert 'match-1' in result.output
    assert 'match-2' not in result.output
    assert '3 more match' in result.output


def test_clickup_find_no_matches_prints_message(runner, watson, mocker):
    _configure_clickup(watson)
    response = mocker.Mock()
    response.status_code = 200
    response.json.return_value = {'tasks': [_mock_task('1', 'unrelated')]}
    mocker.patch('requests.get', return_value=response)

    result = runner.invoke(
        cli.clickup, ['find', 'xyz'], obj=watson)
    assert result.exit_code == 0
    assert 'No matching tasks' in result.output


def test_log_marks_synced_frames(runner, watson):
    synced = _make_frame(watson, tags=['cu:TASK1'])
    unsynced = _make_frame(watson, tags=['cu:TASK2'],
                           start=synced.stop.shift(minutes=5))
    watson.mark_clickup_synced(synced.id, 'E1')
    watson.save()

    result = runner.invoke(
        cli.log,
        ['--from', '2026-04-20', '--to', '2026-04-20', '--no-pager'],
        obj=watson,
    )
    assert result.exit_code == 0, result.output

    lines = {line.split()[0]: line for line in result.output.splitlines()
             if synced.id[:7] in line or unsynced.id[:7] in line}
    assert '\u2713 cu' in lines[synced.id[:7]]
    assert '\u2713 cu' not in lines[unsynced.id[:7]]


def test_clickup_sync_map_persists_across_reloads(runner, watson, config_dir):
    frame = _make_frame(watson, tags=['cu:TASK1'])
    watson.mark_clickup_synced(frame.id, 'E1')
    watson.save()

    # reopen
    from watson import Watson
    reopened = Watson(config_dir=config_dir)
    assert reopened.clickup_sync[frame.id] == 'E1'
