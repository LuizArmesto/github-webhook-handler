#!/usr/bin/env python
import io
import os
import re
import sys
import json
import subprocess
import requests
import ipaddress
import hmac
from hashlib import sha1
from flask import Flask, request, abort
from github import Github

import string
import random

def randompassword():
  chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
  size = random.randint(6, 8)
  return ''.join(random.choice(chars) for x in range(size))

"""
Conditionally import ProxyFix from werkzeug if the USE_PROXYFIX environment
variable is set to true.  If you intend to import this as a module in your own
code, use os.environ to set the environment variable before importing this as a
module.

.. code:: python

    os.environ['USE_PROXYFIX'] = 'true'
    import flask-github-webhook-handler.index as handler

"""
if os.environ.get('USE_PROXYFIX', None) == 'true':
    from werkzeug.contrib.fixers import ProxyFix

class flushfile(object):
  def __init__(self, f):
    self.f = f

  def write(self, x):
    self.f.write(x)
    self.f.flush()

import sys
sys.stdout = flushfile(sys.stdout)

app = Flask(__name__)
app.debug = os.environ.get('DEBUG') == 'true'
if app.debug:
    print("Debug output enabled")
else:
    print("Debug output disabled")

# The repos.json file should be readable by the user running the Flask app,
# and the absolute path should be given by this environment variable.
REPOS_JSON_PATH = os.environ['FLASK_GITHUB_WEBHOOK_REPOS_JSON']
assert json.loads(io.open(REPOS_JSON_PATH, 'r').read())
GITHUB_TOKEN_PATH = os.environ['FLASK_GITHUB_WEBHOOK_GITHUB_TOKEN']
assert io.open(GITHUB_TOKEN_PATH, 'r').read()

@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return 'OK'
    elif request.method == 'POST':
        # Store the IP address of the requester
        request_ip = ipaddress.ip_address(u'{0}'.format(request.remote_addr))

        if app.debug:
            print("Got a request from {}".format(request_ip))

        # If GHE_ADDRESS is specified, use it as the hook_blocks.
        if os.environ.get('GHE_ADDRESS', None):
            hook_blocks = [os.environ.get('GHE_ADDRESS')]
        # Otherwise get the hook address blocks from the API.
        else:
            hook_blocks = requests.get('https://api.github.com/meta').json()[
                'hooks']
            print(hook_blocks)

        # Check if the POST request is from github.com or GHE
        for block in hook_blocks:
            if ipaddress.ip_address(request_ip) in ipaddress.ip_network(block):
                break  # the remote_addr is within the network range of github.
        else:
            if app.debug:
                print("Aborting with a 403")
            abort(403)

        try:
            repos = json.loads(io.open(REPOS_JSON_PATH, 'r').read())
            if app.debug:
                print("Successfully loaded {}".format(REPOS_JSON_PATH))
        except:
            ex_type, ex_value = sys.exc_info()[:2]
            print("Error reading {}:{},{}".format(REPOS_JSON_PATH,ex_type,ex_value))
            abort(403)

        if app.debug:
            print("repos: {}".format(repos))

        try:
            payload = json.loads(request.data.decode())
            if app.debug:
                print("Successfully grokked the payload")
        except:
            ex_type, ex_value = sys.exc_info()[:2]
            print("Error grokking the payload: {},{}".format(ex_type,ex_value))
            abort(403)

        repo_meta = {
            'full_name': payload['repository']['full_name'],
            'clone_url': payload['repository'].get('clone_url', None),
            'random_string': randompassword(),
            'random_string2': randompassword(),
        }

        pull_request =  payload.get('pull_request', None)
        if pull_request:
            repo_meta['issue_number'] = pull_request['number']
            repo_meta['request_sha'] = pull_request['head']['sha']
            repo_meta['request_sha_short'] = pull_request['head']['sha'][:8]
        else:
            repo_meta['issue_number'] = ""
            repo_meta['request_sha'] = ""
            repo_meta['request_sha_short'] = ""

        if app.debug:
            print("repo_meta:  {} ".format(repo_meta))


        event = request.headers.get('X-GitHub-Event')
        if app.debug:
            print("Got a {} event.".format(event))

        if event == "ping":
            return json.dumps({'msg': 'Hi!'})
            
        # Try to match on branch as configured in repos.json
        ref = payload.get('ref', '')
        match = re.match(r"refs/heads/(?P<branch>.*)", ref)
        if match:
            repo_meta['branch'] = match.groupdict()['branch']
        else:
            if app.debug:
                print("No match.")

        if 'branch' in repo_meta:
            repo = repos.get('{}/branch:{}::{}'.format(repo_meta['full_name'], repo_meta['branch'], event), None)
        else:
            repo = repos.get('{}::{}'.format(repo_meta['full_name'], event), None)
        if not repo:
            if app.debug:
                print("Can not find a repo for event type.")
            abort(403)

        if app.debug:
            print("Repo:  {} ".format(repo))

        if not repo:
            if app.debug:
                print("Aborting with a 403 because no repo found")
            abort(403)

        # Check if POST request signature is valid
        key = repo.get('key', None)
        if key:
            if app.debug:
                print("Verifying the key")
            signature = request.headers.get('X-Hub-Signature').split(
                '=')[1]
            if type(key) == str:
                key = key.encode()
            mac = hmac.new(key, msg=request.data, digestmod=sha1)
            if not compare_digest(mac.hexdigest(), signature):
                if app.debug:
                    print("Failed sig check!")
                abort(403)
        else:
            if app.debug:
                print("No key configured for {}".format(repo))

        if repo.get('action', None):
            for action in repo['action']:
                formatedAction = []
                for arg in action:
                    formatedAction.append(arg.format(**repo_meta))

                if app.debug:
                    print("action to run: {}".format(formatedAction))

                subp = subprocess.Popen(formatedAction, cwd=repo.get('path', None))
                subp.wait()

        if repo.get('bot_comment', None):
            github = Github(io.open(GITHUB_TOKEN_PATH, 'r').read())
            online_repo = github.get_repo(repo_meta['full_name'])
            assert online_repo is not None
            issue = online_repo.get_issue(repo_meta['issue_number'])
            if issue is None:
                return "I have no comment on this"
            newComment = repo['bot_comment'].format(**repo_meta)
            print("I will post: '{}' at repo {} and issue #{}".format(newComment, repo_meta['full_name'], repo_meta['issue_number']))
            issue.create_comment(newComment)
            return "I commented something"


        return 'OK'

# Check if python version is less than 2.7.7
if sys.version_info < (2, 7, 7):
    # http://blog.turret.io/hmac-in-go-python-ruby-php-and-nodejs/
    def compare_digest(a, b):
        """
        ** From Django source **

        Run a constant time comparison against two strings

        Returns true if a and b are equal.

        a and b must both be the same length, or False is
        returned immediately
        """
        if len(a) != len(b):
            return False

        result = 0
        for ch_a, ch_b in zip(a, b):
            result |= ord(ch_a) ^ ord(ch_b)
        return result == 0
else:
    compare_digest = hmac.compare_digest

if __name__ == "__main__":
    try:
        port_number = int(sys.argv[1])
    except:
        port_number = 80
    if os.environ.get('USE_PROXYFIX', None) == 'true':
        app.wsgi_app = ProxyFix(app.wsgi_app)
    app.run(host='0.0.0.0', port=port_number)
