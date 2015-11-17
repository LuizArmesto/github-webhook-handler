Flask webhook for Github
########################
A simple github web hook bot that executes commands at specific repository
events. The executed action is configurable per repository. If configured it
posts a comment for new pull requests. This can be used to implement a simple
CI system.

It will also verify that the POST request originated from github.com or a
defined GitHub Enterprise server.  Additionally will ensure that it has a valid
signature (only when the ``key`` setting is properly configured).

Getting started
----------------

Installation Requirements
=========================

Install dependencies found in ``requirements.txt``.

.. code-block:: console

    pip install -r requirements.txt

Repository Configuration
========================

Edit ``repos.json`` to configure repositories, each repository must be
registered under the form ``GITHUB_USER/REPOSITORY_NAME::EVENT``.

.. code-block:: json

    {
        "razius/puppet::push": {
            "path": "/home/puppet",
            "key": "MyVerySecretKey",
            "action": [["git", "pull", "origin", "master"] ],
        },
        "d3non/somerandomexample::pull_request": {
	    "path": "/home/exampleapp",
            "key": "MyVerySecretKey",
	    "action": [["git", "pull", "origin", "live"],
		["echo", "execute", "some", "commands", "..."] ],
      "bot_comment": "Hello world from a bot.<br>I can expand vars: {request_sha} #{issue_number}"
	}
    }

You can find all events at https://developer.github.com/webhooks/

For pull_requests you can specify a ``bot_comment``. The text is expanded with
some useful variables like above. The resulted text will be posted as a new comment
to the related issue.

Runtime Configuration
=====================

Runtime operation is influenced by a set of environment variables which require
being set to influence operation.

Only FLASK_GITHUB_WEBHOOK_REPOS_JSON is required to be set,
as this is required to know how to act on actions from repositories.  The
remaining variables are optional.  USE_PROXYFIX needs to be set to true if
being used behind a WSGI proxy, and is not required otherwise.  GHE_ADDRESS
needs to be set to the IP address of a GitHub Enterprise instance if that is
the source of webhooks.

Set the required environment variables:

.. code-block:: console

    export FLASK_GITHUB_WEBHOOK_REPOS_JSON=/path/to/repos.json
    export FLASK_GITHUB_WEBHOOK_GITHUB_TOKEN=/path/to/github_token

The ``github_token`` file must contain an access token for github (go to
https://github.com/settings/tokens to generate one)


Start the server.

.. code-block:: console

    python3 index.py 80

Start the server behind a proxy (see:
http://flask.pocoo.org/docs/deploying/wsgi-standalone/#proxy-setups)

.. code-block:: console

    USE_PROXYFIX=true python3 index.py 8080

Start the server to be used with a GitHub Enterprise instance.

.. code-block:: console

   GHE_ADDRESS=192.0.2.50 python3 index.py 80


Go to your repository's settings on `github.com <http://github.com>`_ or your
GitHub Enterprise instance and register your public URL under
``Service Hooks -> WebHook URLs``.

Tips & Tricks
~~~~~~~~~~~~~~

If you want to use this with a tunneling service, ngrok_ for example,
you will need to set a GHE_ADDRESS for 127.0.0.1 to allow the tunnel
to post.

.. _ngrok: http://ngrok.com
