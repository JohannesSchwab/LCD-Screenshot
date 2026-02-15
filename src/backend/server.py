import json
import os
import webbrowser
from functools import wraps

import app
import utils.generate_svg as gen
import webview
from flask import Flask, jsonify, render_template, request

gui_dir = os.path.join(
    os.path.dirname(__file__), "..", "..", "gui"
)  # development path

if not os.path.exists(gui_dir):  # frozen executable path
    gui_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui")

server = Flask(__name__, static_folder=gui_dir, template_folder=gui_dir)
server.config["SEND_FILE_MAX_AGE_DEFAULT"] = 1  # disable caching


def verify_token(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        data = json.loads(request.data)
        token = data.get("token")
        if token == webview.token:
            return function(*args, **kwargs)
        else:
            raise Exception("Authentication error")

    return wrapper


@server.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@server.route("/")
def home():
    """
    Render main.html. Initialization is performed asynchronously in initialize() function
    """
    return render_template("main.html", token=webview.token)


@server.route("/init", methods=["POST"])
@verify_token
def initialize():
    """
    Perform heavy-lifting initialization asynchronously.
    :return:
    """
    can_start = app.initialize()

    if can_start:
        response = {
            "status": "ok",
        }
    else:
        response = {"status": "error"}

    return jsonify(response)


@server.route("/choose/path", methods=["POST"])
@verify_token
def choose_path():
    """
    Invoke a folder selection dialog here
    :return:
    """
    dirs = webview.windows[0].create_file_dialog(webview.FileDialog.SAVE)
    if dirs and len(dirs) > 0:
        directory = dirs[0]
        if isinstance(directory, bytes):
            directory = directory.decode("utf-8")

        response = {"status": "ok", "directory": directory}
    else:
        response = {"status": "cancel"}

    return jsonify(response)


@server.route("/save/screenshot", methods=["POST"])
@verify_token
def save_screenshot():
    file = webview.windows[0].create_file_dialog(webview.FileDialog.SAVE)
    if not file or len(file) == 0:
        return jsonify({"status": "cancel"})

    data = request.json["svg-data"]

    success = gen.save_svg(file[0], data)

    if success:
        response = {"status": "ok"}
    else:
        response = {"status": "error"}

    return jsonify(response)


@server.route("/fullscreen", methods=["POST"])
@verify_token
def fullscreen():
    webview.windows[0].toggle_fullscreen()
    return jsonify({})


@server.route("/open-url", methods=["POST"])
@verify_token
def open_url():
    url = request.json["url"]
    webbrowser.open_new_tab(url)

    return jsonify({})


@server.route("/refresh/lcd", methods=["POST"])
@verify_token
def refresh_lcd():
    data = request.json["input-data"]
    result = gen.generate_lcd_svg(
        rows=4,
        cols=20,
        lines=data,
    )
    if result:
        response = {"status": "ok", "result": result}
    else:
        response = {"status": "error"}
    return jsonify(response)


@server.route("/do/stuff", methods=["POST"])
@verify_token
def do_stuff():
    result = app.do_stuff()

    if result:
        response = {"status": "ok", "result": result}
    else:
        response = {"status": "error"}

    return jsonify(response)
