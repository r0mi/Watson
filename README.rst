.. image:: https://tailordev.github.io/Watson/img/logo-watson-600px.png

|Build Status| |PyPI Latest Version| |Requires.io|

Watson is here to help you manage your time. You want to know how
much time you are spending on your projects? You want to generate a nice
report for your client? Watson is here for you.

Wanna know what it looks like? Check this below.

|Watson screenshot|_

Nice isn't it?

Quick start
-----------

Installation
~~~~~~~~~~~~

On OS X, the easiest way to install **watson** is using `Homebrew <http://brew.sh/>`_:

.. code:: bash

  $ brew update && brew install watson

On other platforms, install **watson** using pip or pip3, depending on which one is available:

.. code:: bash

  $ pip install td-watson

or:

.. code:: bash

  $ pip3 install td-watson

If you need more details about installing watson, please refer to the `documentation <https://tailordev.github.io/Watson>`_.

Install from source (this fork)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This fork adds ClickUp integration and is **not** published to PyPI or
Homebrew. The integration currently lives on the ``clickup-integration``
branch, so the clone commands below use ``-b clickup-integration`` to
check it out in one step. Install with `pipx`_ — it gives ``watson``
its own isolated virtualenv and links the binary onto your ``PATH``.

If a packaged Watson is already installed (e.g. ``brew install watson``
or ``pip install td-watson``), uninstall it first so ``which watson``
resolves to the pipx copy.

**macOS**

.. code:: bash

  $ brew install pipx git                         # if not already installed
  $ pipx ensurepath                               # adds ~/.local/bin to PATH
  $ git clone -b clickup-integration git@github.com:r0mi/Watson.git
  $ pipx install -e /path/to/local/Watson         # -e = editable, picks up edits

**Linux**

.. code:: bash

  # Debian/Ubuntu 23.04+:
  $ sudo apt install -y pipx git
  # Fedora:             sudo dnf install -y pipx git
  # Arch:               sudo pacman -S --needed python-pipx git
  # Older distros:      python3 -m pip install --user pipx

  $ pipx ensurepath
  $ git clone -b clickup-integration git@github.com:r0mi/Watson.git
  $ pipx install -e /path/to/local/Watson

**Windows (PowerShell)**

.. code:: powershell

  > py -m pip install --user pipx
  > py -m pipx ensurepath
  > git clone -b clickup-integration git@github.com:r0mi/Watson.git
  > pipx install -e Watson

If you already have a checkout on another branch, switch with
``git switch clickup-integration`` (or ``git checkout clickup-integration``)
before running ``pipx install``.

Verify:

.. code:: bash

  $ watson --version
  2.2.0

Drop ``-e`` if you want a frozen install pinned to the current commit;
re-run ``pipx install`` after each ``git pull`` to refresh. With ``-e``,
edits under ``watson/`` are reflected immediately.

**Shell completion** — see ``watson.completion`` (bash),
``watson.zsh-completion`` (zsh), and ``watson.fish`` (fish) in the repo
root. Install by copying/symlinking into your shell's completion
directory, e.g.::

  # fish
  ln -sf "$(pwd)/watson.fish" ~/.config/fish/completions/watson.fish

  # zsh
  ln -sf "$(pwd)/watson.zsh-completion" \
    /opt/homebrew/share/zsh/site-functions/_watson   # macOS
  # or /usr/share/zsh/site-functions/_watson on Linux

  # bash
  ln -sf "$(pwd)/watson.completion" \
    /opt/homebrew/etc/bash_completion.d/watson        # macOS
  # or /etc/bash_completion.d/watson on Linux

.. _pipx: https://pipx.pypa.io/

Usage
~~~~~

Start tracking your activity via:

.. code:: bash

  $ watson start world-domination +cats

With this command, you have started a new **frame** for the *world-domination* project with the *cats* tag. That's it.

Now stop tracking you world domination plan via:

.. code:: bash

  $ watson stop
  Project world-domination [cats] started 8 minutes ago (2016.01.27 13:00:28+0100)

You can log your latest working sessions (aka **frames**) thanks to the ``log`` command:

.. code:: bash

  $ watson log
  Tuesday 26 January 2016 (8m 32s)
        ffb2a4c  13:00 to 13:08      08m 32s   world-domination  [cats]

Please note that, as `the report command <https://tailordev.github.io/Watson/user-guide/commands/#report>`_, the ``log`` command comes with projects, tags and dates filtering.

To list all available commands, either `read the documentation <https://tailordev.github.io/Watson>`_ or use:

.. code:: bash

  $ watson help

Contributor Code of Conduct
---------------------------

If you want to contribute to this project, please read the project `Contributor Code of Conduct <https://tailordev.github.io/Watson/contributing/coc/>`_

License
-------

Watson is released under the MIT License. See the bundled LICENSE file for
details.

.. |Build Status| image:: https://travis-ci.org/TailorDev/Watson.svg?branch=master
   :target: https://travis-ci.org/TailorDev/Watson
.. |PyPI Latest Version| image:: https://img.shields.io/pypi/v/td-watson.svg
   :target: https://pypi.python.org/pypi/td-watson
.. |Requires.io| image:: https://requires.io/github/TailorDev/Watson/requirements.svg?branch=master
   :target: https://requires.io/github/TailorDev/Watson/requirements/?branch=master
   :alt: Requirements Status
.. |Watson screenshot| image:: https://tailordev.github.io/Watson/img/watson-demo.gif
.. _Watson screenshot: https://asciinema.org/a/35918
