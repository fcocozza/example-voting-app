from flask import Flask, render_template, request, make_response, g
from redis import Redis
import os
import socket
import random
from random import randint
import json
import logging

from statsd import StatsClient
import time

option_a = os.getenv('OPTION_A', "Cats")
option_b = os.getenv('OPTION_B', "Dogs")
hostname = socket.gethostname()

app = Flask(__name__)

gunicorn_error_logger = logging.getLogger('gunicorn.error')
app.logger.handlers.extend(gunicorn_error_logger.handlers)
app.logger.setLevel(logging.INFO)

statsd = StatsClient(host="127.0.0.1", port=8125)

def get_redis():
    if not hasattr(g, 'redis'):
        g.redis = Redis(host="redis", db=0, socket_timeout=5)
    return g.redis

@app.route("/", methods=['POST','GET'])
def hello():
    start=time.time()

    voter_id = request.cookies.get('voter_id')
    if not voter_id:
        voter_id = hex(random.getrandbits(64))[2:-1]

    vote = None

    if request.method == 'POST':
        redis = get_redis()
        vote = request.form['vote']
        app.logger.info('Received vote for %s', vote)
        data = json.dumps({'voter_id': voter_id, 'vote': vote})
        redis.rpush('votes', data)

        app.logger.info("Sending metrics to the statsd server")
        value = randint(0, 100)
        statsd.gauge('my_gauge_metric_vote', value)
        statsd.incr('vote.received_votes')
        app.logger.info("Metric my_gauge_metric_vote sent --> %s", value)
        app.logger.info("Metric vote.received_votes sent")


    resp = make_response(render_template(
        'index.html',
        option_a=option_a,
        option_b=option_b,
        hostname=hostname,
        vote=vote,
    ))
    resp.set_cookie('voter_id', voter_id)

    duration = (time.time() - start) *1000
    statsd.timing("vote.votetime", duration)
    app.logger.info("Metric vote.votetime sent --> %s", duration)
    return resp


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True, threaded=True)
