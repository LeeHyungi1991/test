import datetime
import os
import re
import socket
import sqlite3
import sys
import uuid
from sqlite3 import OperationalError

import mariadb
import requests

# Logger Setting Start
dbserver = "dev.remote.diffspec.net"
dbport = "3306"
dbname = "webmail_secure"


# Logger Setting End


def get_script_folder():
    # path of main .py or .exe when converted with pyinstaller
    if getattr(sys, 'frozen', False):
        script_path = os.path.dirname(sys.executable)
    else:
        script_path = os.path.dirname(
            os.path.abspath(sys.modules['__main__'].__file__)
        )
    return script_path


def connect_to_db_server():
    global dbserver
    global dbport
    global dbname
    try:
        conn = mariadb.connect(
            user="realsecu",
            password="realsecu_01S",
            host=dbserver,  # host="localhost",
            port=int(dbport),
            database=dbname,
            read_timeout=10,
            write_timeout=10,
            connect_timeout=10,
        )
        return conn
    except mariadb.Error as e:
        print(f"Error connecting to MariaDB Platform: {e}")
    return None


def get_cursor(connection):
    return connection.cursor()


# 블랙리스트 새로 추가 시 관리자 이메일로 메일 전송을 위한 함수
# 관리 서버에서 직접 sendmail로 보내기 위해 해당 기능을 구현한 API 도메인으로 POST 요청을 보냄
def send_email_request_to_admin(only_block: bool):
    global dbserver
    # with open("dbconfig/dbserver", "r", encoding='utf-8') as dbserver_file:
    #     dbserver = dbserver_file.readline()
    url = 'https://' + dbserver + '/blacklist/new_item_mail'

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 53))
    myip = s.getsockname()[0]

    datas = {
        'userip': myip,
        'onlyBlock': only_block,
    }

    response = requests.post(url, data=datas)


def get_blacklist(cursor):
    select_count_blacklist_query = "SELECT count(*) FROM blacklist_site;"
    select_all_blacklist_query = "SELECT domain FROM blacklist_site;"

    cursor.execute(select_count_blacklist_query)
    select_count_result = cursor.fetchone()[0]

    if select_count_result != 0:
        cursor.execute(select_all_blacklist_query)

        result_set = cursor.fetchall()
        blacklist_set = [data[0] for data in result_set]

        return blacklist_set

    else:
        return ""


def get_whitelist(cursor):
    select_count_whitelist_query = "SELECT count(*) FROM whitelist_site;"
    select_all_whitelist_query = "SELECT domain FROM whitelist_site;"

    cursor.execute(select_count_whitelist_query)
    select_count_result = cursor.fetchone()[0]

    if select_count_result != 0:
        cursor.execute(select_all_whitelist_query)

        result_set = cursor.fetchall()
        whitelist_set = [data[0] for data in result_set]

        return whitelist_set

    else:
        return ""


def get_policy(cursor):
    select_policy_query = "SELECT policy_on, policy_off FROM policy_setting;"
    cursor.execute(select_policy_query)

    result_set = cursor.fetchone()

    policy_set = []
    policy_on = result_set[0]
    policy_off = result_set[1]

    policy_set.append(policy_on)
    policy_set.append(policy_off)

    return policy_set


# mailpage_judge.py 4) 에서 사용할 데이터 관련
def get_string_from(cursor):
    select_all_string_from_query = "SELECT name FROM string_from"
    cursor.execute(select_all_string_from_query)

    result_set = cursor.fetchall()
    string_from_set = [data[0] for data in result_set]

    return string_from_set


def get_string_to(cursor):
    select_all_string_to_query = "SELECT name FROM string_to"
    cursor.execute(select_all_string_to_query)

    result_set = cursor.fetchall()
    string_to_set = [data[0] for data in result_set]

    return string_to_set


def get_string_cc(cursor):
    select_all_string_cc_query = "SELECT name FROM string_cc"
    cursor.execute(select_all_string_cc_query)

    result_set = cursor.fetchall()
    string_cc_set = [data[0] for data in result_set]

    return string_cc_set


def get_string_subject(cursor):
    select_all_string_subject_query = "SELECT name FROM string_subject"
    cursor.execute(select_all_string_subject_query)

    result_set = cursor.fetchall()
    string_subject_set = [data[0] for data in result_set]

    return string_subject_set


def get_string_body(cursor):
    select_all_string_body_query = "SELECT name FROM string_body"
    cursor.execute(select_all_string_body_query)

    result_set = cursor.fetchall()
    string_body_set = [data[0] for data in result_set]

    return string_body_set


def insert_log(connection, cursor, policy, domain, rcv_domain_ip, rcv_country, rcv_country_long, result):
    # 내부 IP 알아내기
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 53))
    myip = s.getsockname()[0]

    insert_log_query = "INSERT INTO secure_log (date, ip, policy, domain, domain_ip, country, country_long, result) VALUES (NOW(), ?, ?, ?, ?, ?, ?, ?)"
    cursor.execute(insert_log_query, (myip, policy, domain, rcv_domain_ip, rcv_country, rcv_country_long, result))
    connection.commit()


def insert_blcaklist(connection, cursor, domain, only_block):
    if not only_block:
        insert_blacklist_query = "INSERT INTO blacklist_site (date, domain) VALUES (NOW(), '" + domain + "')"
        select_count_query = "SELECT COUNT(*) FROM blacklist_site WHERE domain='" + domain + "';"
        cursor.execute(select_count_query)
        select_count_result = cursor.fetchone()[0]
        if select_count_result == 0:
            cursor.execute(insert_blacklist_query)
            connection.commit()
            send_email_request_to_admin(only_block)
    else:
        send_email_request_to_admin(only_block)


def get_domain_log_latest_time(cursor, domain):
    select_count_query = "SELECT count(*) FROM secure_log WHERE domain='" + domain + "'"
    select_time_query = "SELECT DATE FROM secure_log WHERE domain='" + domain + "' ORDER BY date DESC"

    cursor.execute(select_count_query)
    select_count_result = cursor.fetchone()[0]

    if select_count_result != 0:
        cursor.execute(select_time_query)
        select_time_result = cursor.fetchone()[0]

        return select_time_result

    return "no_log_before"


# 언어 기반 차단 관련 DB 쿼리 함수들 시작
def get_label_from(cursor):
    # TODO
    select_all_label_from_query = "SELECT name FROM label_from"
    cursor.execute(select_all_label_from_query)

    result_set = cursor.fetchall()
    # label_from_set = [data[0] for data in result_set]
    label_from_set = {data[0] for data in result_set}

    return label_from_set


def get_label_to(cursor):
    # TODO
    select_all_label_to_query = "SELECT name FROM label_to"
    cursor.execute(select_all_label_to_query)

    result_set = cursor.fetchall()
    # label_to_set = [data[0] for data in result_set]
    label_to_set = {data[0] for data in result_set}

    return label_to_set


def get_label_cc(cursor):
    # TODO
    select_all_label_cc_query = "SELECT name FROM label_cc"
    cursor.execute(select_all_label_cc_query)

    result_set = cursor.fetchall()
    # label_cc_set = [data[0] for data in result_set]
    label_cc_set = {data[0] for data in result_set}

    return label_cc_set


def get_label_hidden_cc(cursor):
    # TODO
    select_all_label_hidden_cc_query = "SELECT name FROM label_hidden_cc"
    cursor.execute(select_all_label_hidden_cc_query)

    result_set = cursor.fetchall()
    # label_hidden_cc_set = [data[0] for data in result_set]
    label_hidden_cc_set = {data[0] for data in result_set}

    return label_hidden_cc_set


def get_label_title(cursor):
    # TODO
    select_all_label_title_query = "SELECT name FROM label_title"
    cursor.execute(select_all_label_title_query)

    result_set = cursor.fetchall()
    # label_title_set = [data[0] for data in result_set]
    label_title_set = {data[0] for data in result_set}

    return label_title_set


def get_label_content(cursor):
    # TODO
    select_all_label_content_query = "SELECT name FROM label_content"
    cursor.execute(select_all_label_content_query)

    result_set = cursor.fetchall()
    # label_content_set = [data[0] for data in result_set]
    label_content_set = {data[0] for data in result_set}

    return label_content_set


def get_label_file(cursor):
    # TODO
    select_all_label_file_query = "SELECT name FROM label_file"
    cursor.execute(select_all_label_file_query)

    result_set = cursor.fetchall()
    # label_file_set = [data[0] for data in result_set]
    label_file_set = {data[0] for data in result_set}

    return label_file_set


def get_label_send(cursor):
    # TODO
    select_all_label_send_query = "SELECT name FROM label_send"
    cursor.execute(select_all_label_send_query)

    result_set = cursor.fetchall()
    # label_send_set = [data[0] for data in result_set]
    label_send_set = {data[0] for data in result_set}

    return label_send_set


def get_engine_integrity_checklist(cursor):
    # TODO
    select_all_label_file_query = "SELECT keyname, filename, path, value FROM engine_integrity_check;"
    cursor.execute(select_all_label_file_query)

    result_set = cursor.fetchall()
    # label_file_set = [data[0] for data in result_set]
    label_file_list = [
        {
            "keyname": data[0],
            "filename": data[1],
            "path": data[2],
            "value": data[3],
        }
        for data in result_set]
    return label_file_list


def close_db_server(connection):
    try:
        connection.close()
    except:
        pass


def get_local_connection():
    local_connection = sqlite3.connect("./local_temp_data.db", isolation_level=None)
    return local_connection


def initialize_to_local_db_server():
    try:
        local_connection = get_local_connection()
        cursor_loc = local_connection.cursor()

        # cursor_loc.execute("DROP TABLE IF EXISTS policy_setting;")
        cursor_loc.execute(
            "CREATE TABLE IF NOT EXISTS policy_setting (id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(512) NOT NULL, value VARCHAR(512) NOT NULL);")
        # cursor_loc.execute("DROP TABLE IF EXISTS whitelist_site;")
        cursor_loc.execute(
            "CREATE TABLE IF NOT EXISTS whitelist_site (id INTEGER PRIMARY KEY AUTOINCREMENT, domain VARCHAR(512) NOT NULL);")

        # cursor_loc.execute("DROP TABLE IF EXISTS blacklist_site;")
        cursor_loc.execute(
            "CREATE TABLE IF NOT EXISTS blacklist_site (id INTEGER PRIMARY KEY AUTOINCREMENT, domain VARCHAR(512) NOT NULL);")

        # cursor_loc.execute("DROP TABLE IF EXISTS label_from;")
        cursor_loc.execute(
            "CREATE TABLE IF NOT EXISTS label_from (id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(512) NOT NULL);")

        # cursor_loc.execute("DROP TABLE IF EXISTS label_to;")
        cursor_loc.execute(
            "CREATE TABLE IF NOT EXISTS label_to (id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(512) NOT NULL);")

        # cursor_loc.execute("DROP TABLE IF EXISTS label_cc;")
        cursor_loc.execute(
            "CREATE TABLE IF NOT EXISTS label_cc (id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(512) NOT NULL);")

        # cursor_loc.execute("DROP TABLE IF EXISTS label_hidden_cc;")
        cursor_loc.execute(
            "CREATE TABLE IF NOT EXISTS label_hidden_cc (id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(512) NOT NULL);")

        # cursor_loc.execute("DROP TABLE IF EXISTS label_title;")
        cursor_loc.execute(
            "CREATE TABLE IF NOT EXISTS label_title (id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(512) NOT NULL);")

        # cursor_loc.execute("DROP TABLE IF EXISTS label_content;")
        cursor_loc.execute(
            "CREATE TABLE IF NOT EXISTS label_content (id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(512) NOT NULL);")

        # cursor_loc.execute("DROP TABLE IF EXISTS label_file;")
        cursor_loc.execute(
            "CREATE TABLE IF NOT EXISTS label_file (id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(512) NOT NULL);")

        # cursor_loc.execute("DROP TABLE IF EXISTS label_send;")
        cursor_loc.execute(
            "CREATE TABLE IF NOT EXISTS label_send (id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(512) NOT NULL);")

        cursor_loc.close()
        local_connection.close()
    except OperationalError as e:
        print(e)


def get_mac_address():
    mac_address = ':'.join(re.findall('..', '%012x' % uuid.getnode()))
    return mac_address


def sync_from_mainDB_to_localDB(engine_version):
    try:
        main_connection = connect_to_db_server()
        local_connection = get_local_connection()

        cursor_main = main_connection.cursor()
        cursor_loc = local_connection.cursor()

        cursor_loc.execute("DELETE FROM policy_setting;")
        cursor_main.execute("SELECT * FROM policy_setting;")
        local_connection.commit()
        main_connection.commit()
        result_set = cursor_main.fetchall()
        for data in result_set:
            cursor_loc.execute("INSERT INTO policy_setting VALUES (?,?,?);", (None, data[1], data[2]))

        cursor_loc.execute("DELETE FROM whitelist_site;")
        cursor_main.execute("SELECT * FROM whitelist_site;")
        result_set = cursor_main.fetchall()
        for data in result_set:
            cursor_loc.execute("INSERT INTO whitelist_site VALUES (?,?);", (None, data[2]))

        cursor_loc.execute("DELETE FROM blacklist_site;")
        cursor_main.execute("SELECT * FROM blacklist_site;")
        result_set = cursor_main.fetchall()
        for data in result_set:
            cursor_loc.execute("INSERT INTO blacklist_site VALUES (?,?);", (None, data[2]))

        cursor_loc.execute("DELETE FROM label_from;")
        cursor_main.execute("SELECT * FROM label_from;")
        result_set = cursor_main.fetchall()
        for data in result_set:
            cursor_loc.execute("INSERT INTO label_from VALUES (?,?);", (None, data[1]))

        cursor_loc.execute("DELETE FROM label_to;")
        cursor_main.execute("SELECT * FROM label_to;")
        result_set = cursor_main.fetchall()
        for data in result_set:
            cursor_loc.execute("INSERT INTO label_to VALUES (?,?);", (None, data[1]))

        cursor_loc.execute("DELETE FROM label_cc;")
        cursor_main.execute("SELECT * FROM label_cc;")
        result_set = cursor_main.fetchall()
        for data in result_set:
            cursor_loc.execute("INSERT INTO label_cc VALUES (?,?);", (None, data[1]))

        cursor_loc.execute("DELETE FROM label_hidden_cc;")
        cursor_main.execute("SELECT * FROM label_hidden_cc;")
        result_set = cursor_main.fetchall()
        for data in result_set:
            cursor_loc.execute("INSERT INTO label_hidden_cc VALUES (?,?);", (None, data[1]))

        cursor_loc.execute("DELETE FROM label_title;")
        cursor_main.execute("SELECT * FROM label_title;")
        result_set = cursor_main.fetchall()
        for data in result_set:
            cursor_loc.execute("INSERT INTO label_title VALUES (?,?);", (None, data[1]))

        cursor_loc.execute("DELETE FROM label_content;")
        cursor_main.execute("SELECT * FROM label_content;")
        result_set = cursor_main.fetchall()
        for data in result_set:
            cursor_loc.execute("INSERT INTO label_content VALUES (?,?);", (None, data[1]))

        cursor_loc.execute("DELETE FROM label_file;")
        cursor_main.execute("SELECT * FROM label_file;")
        result_set = cursor_main.fetchall()
        for data in result_set:
            cursor_loc.execute("INSERT INTO label_file VALUES (?,?);", (None, data[1]))

        cursor_loc.execute("DELETE FROM label_send;")
        cursor_main.execute("SELECT * FROM label_send;")
        result_set = cursor_main.fetchall()
        for data in result_set:
            cursor_loc.execute("INSERT INTO label_send VALUES (?,?);", (None, data[1]))

        cursor_main.close()
        cursor_loc.close()
    except OperationalError as o:
        print(o)

