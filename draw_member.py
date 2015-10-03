import csv
from datetime import datetime
import random
import sqlite3
from flask import Flask, g, render_template, request

app = Flask(__name__)
SQLITE_DB_PATH = 'members.db'
SQLITE_DB_SCHEMA = 'create_db.sql'
MEMBER_CSV_PATH = 'members.csv'


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/draw', methods=['POST'])
def draw():
    # Get the database connection
    db = get_db()

    # Draw member ids from given group
    # If ALL is given then draw from all members
    group_name = request.form.get('group_name', 'ALL')
    valid_members_sql = 'SELECT id FROM members '
    if group_name == 'ALL':
        cursor = db.execute(valid_members_sql)
    else:
        valid_members_sql += 'WHERE group_name = ?'
        cursor = db.execute(valid_members_sql, (group_name, ))
    valid_member_ids = [
        row[0] for row in cursor
    ]

    # If no valid members return 404 (unlikely)
    if not valid_member_ids:
        err_msg = "<p>No member in group '%s'</p>" % group_name
        return err_msg, 404

    # Randomly choice a member
    lucky_member_id = random.choice(valid_member_ids)

    # Obtain the lucy member's information
    member_name, member_group_name = db.execute(
        'SELECT name, group_name FROM members WHERE id = ?',
        (lucky_member_id, )
    ).fetchone()

    # Update draw history
    with db:
        db.execute('INSERT INTO draw_histories (memberid) VALUES (?)',
                   (lucky_member_id, ))

    # Render template
    return render_template(
        'draw.html',
        name=member_name,
        group=member_group_name,
    )


@app.route('/history')
def history():
    db = get_db()
    c = db.execute(
        'SELECT m.name, m.group_name, d.time AS "draw_time [timestamp]"'
        'FROM draw_histories AS d, members as m '
        'WHERE m.id == d.memberid '
        'ORDER BY d.time DESC '
        'LIMIT 10'
    )
    recent_histories = []
    for row in c:
        recent_histories.append({
            'name': row[0],
            'group': row[1],
            'draw_time': datetime.strptime(row[2], '%Y-%m-%d %H:%M:%S'),
        })
    return render_template('history.html', recent_histories=recent_histories)


# SQLite3-related operations
# See SQLite3 usage pattern from Flask official doc
# http://flask.pocoo.org/docs/0.10/patterns/sqlite3/
def get_db():
    """Get the SQLite database connection.

    If called outside Flask, e.g. Python shell,
    one should wrap it with app.app_context()::

        # Get all members
        with app.app_context():
            db = get_db()
            for row in db.execute('SELECT * FROM members'):
                print(row)

    Use the return value out of app_context() will raise
    `sqlite3.ProgrammingError` because the database connection
    is closed::

        db.execute('...')
    """
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(SQLITE_DB_PATH)
        # Enable foreign key check
        db.execute("PRAGMA foreign_keys = ON")
    return db


def reset_db():
    with open(SQLITE_DB_SCHEMA, 'r') as f:
        create_db_sql = f.read()
    db = get_db()
    # Reset database
    # Note that CREATE/DROP table are *immediately* committed
    # even inside a transaction
    with db:
        db.execute("DROP TABLE IF EXISTS draw_histories")
        db.execute("DROP TABLE IF EXISTS members")
        db.executescript(create_db_sql)

    # Read members CSV data
    with open(MEMBER_CSV_PATH, newline='') as f:
        csv_reader = csv.DictReader(f)
        members = [
            (row['名字'], row['團體'])
            for row in csv_reader
        ]
    # Write members into database
    with db:
        db.executemany(
            'INSERT INTO members (name, group_name) VALUES (?, ?)',
            members
        )


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


if __name__ == '__main__':
    app.run(debug=True)
