import sys
import base64
sys.path.append('..')
import logging
import base64
from flask import send_file
from io import BytesIO
import zipfile
from zipfile import ZipFile
import requests
import subprocess
import os
import argparse
from flask import Flask, send_from_directory, request, jsonify, redirect, render_template, url_for, make_response


app = Flask(__name__, static_folder='static')

app.logger.setLevel(logging.ERROR)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

messages = []


def send_msg(role, text):
    try:
        data = {"role": role, "text": text}
        response = requests.post("http://127.0.0.1:8000/send_message", json=data)
        if response.status_code == 200:
            print("Message sent successfully!")
        else:
            print("Failed to send message.")
    except:
        logging.info("flask app.py did not start for online log")


@app.route("/")
def index():
    return render_template('index.html')
    # return send_from_directory("static", "index.html")


@app.route("/chain_visualizer")
def chain_visualizer():
    return render_template("chain_visualizer.html")

@app.route("/replay")
def replay():
    return render_template("replay.html", file = None, folder_name = None)

@app.route("/get_messages")
def get_messages():
    return jsonify(messages)

@app.route('/process-task', methods = ['POST', "GET"])
def process_task():
    if request.method == 'POST':
        task = request.form['task']
        project = request.form['project']

        parser = argparse.ArgumentParser(description='argparse')
        parser.add_argument('--config', type=str, default="Agile",
                            help="Name of config, which is used to load configuration under CompanyConfig/")
        parser.add_argument('--org', type=str, default="DefaultOrganization",
                            help="Name of organization, your software will be generated in WareHouse/name_org_timestamp")
        parser.add_argument('--task', type=str, default="Develop a basic Gomoku game.",
                            help="Prompt of software")
        parser.add_argument('--name', type=str, default="Gomoku",
                            help="Name of software, your software will be generated in WareHouse/name_org_timestamp")
        parser.add_argument('--model', type=str, default="GPT_3_5_AZURE",
                            help="GPT Model, choose from {'GPT_3_5_TURBO','GPT_4','GPT_4_32K', 'GPT_3_5_AZURE'}")
        args = parser.parse_args()
        args.task = task
        dir_path = run_task(args)
        folder_name = os.path.basename(dir_path)
        full_path = os.path.join(dir_path, folder_name + '.log')
        with open(full_path) as f:
            content = f.read().encode()
        content = base64.b64encode(content).decode('utf-8')
        return render_template("replay.html", file = content, folder_name = dir_path)
    else:
        return redirect(url_for('index'))
@app.route('/download')
def download():
    folder_name = request.args.get('folder_name')
    all_files = os.listdir(folder_name)
    stream = BytesIO()
    with ZipFile(stream, 'w') as zf:
        for file in all_files:
            zf.write(os.path.join(folder_name, file), os.path.basename(file))
    stream.seek(0)

    return send_file(
        stream,
        download_name='downloaded.zip',
        as_attachment=True,
        mimetype='application/zip'
    )

@app.route("/send_message", methods=["POST"])
def send_message():
    data = request.get_json()
    role = data.get("role")
    text = data.get("text")

    avatarUrl = find_avatar_url(role)

    message = {"role": role, "text": text, "avatarUrl": avatarUrl}
    messages.append(message)
    return jsonify(message)


def find_avatar_url(role):
    role = role.replace(" ", "%20")
    avatar_filename = f"avatars/{role}.png"
    avatar_url = f"/static/{avatar_filename}"
    return avatar_url


if __name__ == "__main__":
    from run_api import run_task
    print("please visit http://127.0.0.1:8000/ for demo")
    app.run(debug=False, port=8000)
