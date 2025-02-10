import sqlite3
from flask import Flask, request, render_template, url_for, redirect, send_from_directory

app = Flask(__name__)

admin_code = "1234"
just_user_code = "1111"
is_logged = False
this_user = {}


def convert_inventory_into_list(type):
    conn = get_db_connection()
    cursor = conn.cursor()

    inventory = {}
    inventory_names = cursor.execute('SELECT db_name, COUNT(db_name) FROM db_inventory '
                                     'WHERE db_type = ? GROUP BY db_name', (type,)).fetchall()
    for one in inventory_names:
        things = cursor.execute('SELECT * FROM db_inventory WHERE db_type = ? AND db_name = ?',
                                (type, one['db_name'],)).fetchall()
        inventory[one['db_name']] = {'count': one['COUNT(db_name)'], 'things': things}

    conn.commit()
    conn.close()
    return inventory


def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('CREATE TABLE IF NOT EXISTS db_users (db_id INTEGER PRIMARY KEY AUTOINCREMENT, '
                   'db_user_type TEXT NOT NULL, db_login TEXT NOT NULL, db_password TEXT NOT NULL, '
                   'db_name TEXT NOT NULL, db_work TEXT NOT NULL, db_id_inventory TEXT)')

    cursor.execute('CREATE TABLE IF NOT EXISTS db_inventory (db_id INTEGER PRIMARY KEY AUTOINCREMENT, '
                   'db_type TEXT NOT NULL, db_name TEXT NOT NULL, db_user TEXT, db_problem_description TEXT)')

    cursor.execute('CREATE TABLE IF NOT EXISTS db_bought_inventory (db_id INTEGER PRIMARY KEY AUTOINCREMENT, '
                   'db_name TEXT NOT NULL, db_category TEXT NOT NULL, db_count INT NOT NULL, db_price INT NOT NULL, '
                   'db_producer TEXT NOT NULL)')

    cursor.execute('CREATE TABLE IF NOT EXISTS db_notice (db_id INTEGER PRIMARY KEY AUTOINCREMENT, '
                   'db_main TEXT NOT NULL, db_sender TEXT NOT NULL, db_recipient TEXT NOT NULL)')

    cursor.execute('CREATE TABLE IF NOT EXISTS db_max_index (db_max_index INT NOT NULL)')
    max_index = cursor.execute('SELECT db_max_index FROM db_max_index').fetchone()
    if max_index is None:
        cursor.execute('INSERT INTO db_max_index (db_max_index) VALUES (?)', (0,))

    conn.commit()
    conn.close()


init_db()


# -------------- Вход и регистрация --------------
@app.route('/', methods=['GET', 'POST'])
def index():
    global is_logged, this_user

    is_logged = False
    this_user = None

    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']

        if len(login) == 0 or len(password) == 0:
            return render_template('index.html', error="Все поля должны быть заполнены")

        conn = get_db_connection()
        cursor = conn.cursor()
        user = cursor.execute('SELECT * FROM db_users WHERE db_login = ?', (login,)).fetchone()
        conn.commit()
        conn.close()

        if user is None:
            return render_template('index.html', error="Логин не нйден")

        if password != user['db_password']:
            return render_template('index.html', error="Неверный пароль")

        if user['db_user_type'] == "admin":
            file = "admin.html"
        else:
            file = "just_user.html"

        is_logged = True
        this_user = user
        return render_template(file, user=this_user)

    return render_template('index.html')


@app.route('/register<user_type>', methods=['GET', 'POST'])
def register(user_type):
    global is_logged, this_user, admin_code, just_user_code

    if user_type == "admin":
        file = "admin.html"
        work_text = "Ваша должность"
        user_name = "Администратора"
        user_type_text = "администратор"
        true_code = admin_code
    else:
        file = "just_user.html"
        work_text = "Введите класс с буквой"
        user_name = "Пользователя"
        user_type_text = "пользователь"
        true_code = just_user_code

    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor()

        login = request.form['login']
        password1 = request.form['password1']
        password2 = request.form['password2']
        name = request.form['name']
        work = request.form['work']
        code = request.form['code']

        for one in [login, password1, password2, name, work, code]:
            if len(one) == 0:
                error = "Все поля должны быть заполнены!"
                return render_template('register.html', user=user_name, work_text=work_text, error=error)

        users = cursor.execute('SELECT db_login, db_name FROM db_users WHERE db_login = ? OR db_name = ?',
                               (login, name)).fetchone()
        if users is not None or name == "admins":
            error = "Логин или имя заняты!"
            return render_template('register.html', user=user_name, work_text=work_text, error=error)

        if password1 != password2:
            error = "Пароли не свпадают!"
            return render_template('register.html', user=user_name, work_text=work_text, error=error)

        if code != true_code:
            error = f"Неверный код {user_name}!"
            return render_template('register.html', user=user_name, work_text=work_text, error=error)

        cursor.execute('INSERT INTO db_users (db_user_type, db_login, db_password, db_name, db_work) '
                       ' VALUES (?, ?, ?, ?, ?)', (user_type, login, password1, name, work))
        conn.commit()
        user = cursor.execute('SELECT * FROM db_users WHERE db_login = ?', (login,)).fetchone()

        main_text = f"Добавился новый {user_type_text} {name} - {work}"
        cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES '
                       '(?, "Системы Оповещений", "admins")', (main_text,))

        conn.commit()
        conn.close()

        is_logged = True
        this_user = user
        return render_template(file, user=user)

    return render_template('register.html', user_name=user_name, work_text=work_text)


# -------------- Вход и регистрация --------------


# -------------- users --------------
@app.route('/admin')
def admin():
    global is_logged, this_user
    if not is_logged:
        return redirect(url_for('index'))
    return render_template('admin.html', user=this_user)


@app.route('/just_user')
def just_user():
    global is_logged, this_user
    if not is_logged:
        return redirect(url_for('index'))
    return render_template('just_user.html', user=this_user)


# -------------- users --------------


@app.route('/notification')
def notification():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if this_user['db_user_type'] == "admin":
        notice = cursor.execute('SELECT * FROM db_notice WHERE db_recipient = "admins" ORDER BY db_id').fetchall()
    else:
        notice = cursor.execute('SELECT * FROM db_notice WHERE db_recipient = ? ORDER BY db_id',
                                (this_user['db_name'],)).fetchall()

    null_notice = ""
    if len(notice) == 0:
        null_notice = "У вас пока нет уведомлений"

    back_file = this_user['db_user_type']
    return render_template('notification.html', user=this_user, notice=notice, null_notice=null_notice,
                           back_file=back_file)


# -------------- inventory --------------
@app.route('/names_free_inventory')
def names_free_inventory():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    inv_free = cursor.execute('SELECT db_name, COUNT(db_name) AS count FROM db_inventory WHERE db_type = "free"'
                              'GROUP BY db_name').fetchall()
    null_free_names = ""
    if len(inv_free) == 0:
        null_free_names = "Нет доступного инвентаря!"

    conn.commit()
    conn.close()

    return render_template('names_free_inventory.html', user=this_user, inv_free=inv_free,
                           null_free_names=null_free_names)


@app.route('/inventory_all')
def inventory_all():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    null_all = ""
    conn = get_db_connection()
    cursor = conn.cursor()

    inventory_names = cursor.execute('SELECT db_name, COUNT(db_name) FROM db_inventory GROUP BY db_name').fetchall()

    inventory = {}
    for name in inventory_names:
        things_free = cursor.execute('SELECT * FROM db_inventory WHERE db_name = ? AND db_type = "free"',
                                     (name['db_name'],)).fetchall()
        count_free = len(things_free)

        things_usefull = cursor.execute('SELECT * FROM db_inventory WHERE db_name = ? AND db_type = "usefull"',
                                        (name['db_name'],)).fetchall()
        count_usefull = len(things_usefull)

        things_broken = cursor.execute('SELECT * FROM db_inventory WHERE db_name = ? AND db_type = ?',
                                       (name['db_name'], "broken")).fetchall()
        count_broken = len(things_broken)

        inventory[name['db_name']] = {'count': name['COUNT(db_name)'],
                                      'free': {'count': count_free, 'things': things_free},
                                      'usefull': {'count': count_usefull, 'things': things_usefull},
                                      'broken': {'count': count_broken, 'things': things_broken}}

    if len(inventory) == 0:
        null_all = "Нет инвентаря"

    conn.commit()
    conn.close()
    return render_template('inventory_all.html', user=this_user, inventory=inventory, null_all=null_all)


@app.route('/inventory_free')
def inventory_free():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    null_free = ""
    inv_free = convert_inventory_into_list("free")
    if len(inv_free) == 0:
        null_free = "Нет свободного инвентаря!"

    return render_template('inventory_free.html', user=this_user, inv_free=inv_free, null_free=null_free)


@app.route('/inventory_usefull')
def inventory_usefull():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    null_usefull = ""
    inv_usefull = convert_inventory_into_list("usefull")
    if len(inv_usefull) == 0:
        null_usefull = "Нет закреплённого инвентаря!"

    return render_template('inventory_usefull.html', user=this_user, inv_usefull=inv_usefull, null_usefull=null_usefull)


@app.route('/inventory_broken')
def inventory_broken():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    null_broken = ""
    inv_broken = convert_inventory_into_list("broken")
    if len(inv_broken) == 0:
        null_broken = "Нет сломанного инвентаря!"

    return render_template('inventory_broken.html', user=this_user, inv_broken=inv_broken, null_broken=null_broken)


@app.route('/my_inventory')
def my_inventory():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    null_my = ""
    my_inv = cursor.execute('SELECT * FROM db_inventory WHERE db_user = ?', (this_user['db_name'],)).fetchall()
    if len(my_inv) == 0:
        null_my = "У вас ещё нет инвентаря!"
    conn.commit()
    conn.commit()

    return render_template('my_inventory.html', user=this_user, my_inv=my_inv, null_my=null_my)


# -------------- inventory --------------


@app.route('/show_users')
def show_users():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    admins = cursor.execute('SELECT * FROM db_users WHERE db_user_type = "admin" AND NOT db_login = ?',
                            (this_user['db_login'],)).fetchall()
    just_users = cursor.execute('SELECT * FROM db_users WHERE db_user_type = "just_user"').fetchall()
    conn.commit()
    conn.close()

    just_users_whith_inv = []
    just_users_whithout_inv = []

    for one in just_users:
        if one['db_id_inventory'] is None:
            just_users_whithout_inv.append(one)
        else:
            just_users_whith_inv.append(one)

    null_admins = ""
    null_just_users = ""
    if len(admins) == 0:
        null_admins = "Нет других администраторов!"
    if len(just_users) == 0:
        null_just_users = "Пока нет пользователей!"

    print(just_users_whith_inv)
    print(just_users_whithout_inv)

    return render_template('show_users.html', user=this_user, admins=admins,
                           just_users_whith_inv=just_users_whith_inv,
                           just_users_whithout_inv=just_users_whithout_inv,
                           null_admins=null_admins, null_just_users=null_just_users)


@app.route('/bought_plan', methods=['GET', 'POST'])
def bought_plan():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    ids = cursor.execute('SELECT db_id, COUNT(db_id) FROM db_bought_inventory').fetchall()[0][1]

    plans = []
    if ids != 0:
        for idd in range(1, ids + 1):
            plan = cursor.execute('SELECT * FROM db_bought_inventory WHERE db_id = ?', (idd,)).fetchall()
            plans.append(plan[0])

    conn.close()

    if request.method == 'POST':
        item = request.form['itemName']
        category = request.form['itemCategory']
        price = request.form['price']
        count = request.form['count']
        postav = request.form['supplier']

        if int(price) <= 0:
            return render_template('planzakupki.html', plans=plans,
                                   error="Невозможное значение цены!")

        if int(count) <= 0:
            return render_template('planzakupki.html', plans=plans,
                                   error="Невозможное значение количества!")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO db_bought_inventory (db_name, db_category, db_count, db_price, db_producer) '
                       ' VALUES (?, ?, ?, ?, ?)', (item, category, count, price, postav))

        main_text = f"Добавлено в закупки: {item} ({category}) - по цене {price} руб. " \
                    f"в количестве {count} шт. - от {postav} "
        cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES (?, ?, "admins")',
                       (main_text, this_user['db_name']))

        conn.commit()
        conn.close()
        return redirect(url_for('bought_plan'))

    return render_template('planzakupki.html', user=this_user, plans=plans)


@app.route('/reports')
def reports():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    max_index = cursor.execute('SELECT db_max_index FROM db_max_index').fetchone()['db_max_index']
    conn.commit()
    conn.close()

    null_reports = ""
    if max_index == 0:
        null_reports = "Нет отчётов!"

    return render_template('reports.html', user=this_user, max_index=max_index, null_reports=null_reports)


@app.route('/download_report<index>')
def download_report(index):
    global is_logged

    if not is_logged:
        return redirect(url_for('index'))

    file_name = "report" + index + ".txt"
    print(file_name)
    return send_from_directory('reports_files', file_name, as_attachment=True)


@app.route('/add_report')
def add_report():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    max_index = cursor.execute('SELECT db_max_index FROM db_max_index').fetchone()['db_max_index'] + 1
    cursor.execute('UPDATE db_max_index SET db_max_index = ?', (max_index,))

    file = open(f'reports_files/report{max_index}.txt', 'w')
    # <---- main_text ---->
    file.write(f"!!Система управления спортивным инвентарём!!\n\nОтчёт №{max_index}\n"
               f"Создатель: {this_user['db_name']}, должность: {this_user['db_work']}\n\nТело отчёта:")

    # -- users --
    admins = cursor.execute('SELECT * FROM db_users WHERE db_user_type = "admin"').fetchall()
    just_users = cursor.execute('SELECT * FROM db_users WHERE db_user_type = "just_user"').fetchall()

    file.write("\n\n<-- Список всех пользователей -->")

    file.write("\nСписок администраторов:")
    for admin in admins:
        file.write(f"\n   {admin['db_name']} - {admin['db_work']};")

    file.write("\nСписок обычных пользователей:")
    for just_user in just_users:
        if just_user['db_id_inventory'] is not None:
            ids = just_user['db_id_inventory'].split(" ")
            file.write(f"\n   {just_user['db_name']} - {just_user['db_work']}, "
                       f"использует инвентарь с ID: {', '.join(id for id in ids)};")
        else:
            file.write(f"\n   {just_user['db_name']} - {just_user['db_work']};")
    if len(just_users) == 0:
        file.write("\n    Нет пользователей!")
    # -- users --

    # -- inventory --
    inv_free = convert_inventory_into_list("free")
    inv_usefull = convert_inventory_into_list("usefull")
    inv_broken = convert_inventory_into_list("broken")

    file.write("\n\n<-- Список всего инвентаря в наличии -->")

    file.write("\nДоступный инвентарь:")
    for name in inv_free.keys():
        file.write(f"\n    {name} ({inv_free[name]['count']} шт.):")
        for thing in inv_free[name]['things']:
            file.write(f"\n        ID - {thing['db_id']};")
    if len(inv_free) == 0:
        file.write("\n    Нет свободного инвентаря!")

    file.write("\nИспользуемый инвентарь:")
    for name in inv_usefull.keys():
        file.write(f"\n    {name} ({inv_usefull[name]['count']} шт.):")
        for thing in inv_usefull[name]['things']:
            file.write(f"\n        ID - {thing['db_id']}, использует - {thing['db_user']};")
    if len(inv_usefull) == 0:
        file.write("\n    Нет используемого инвентаря!")

    file.write("\nСломанный инвентарь:")
    for name in inv_broken.keys():
        file.write(f"\n    {name} ({inv_broken[name]['count']} шт.):")
        for thing in inv_broken[name]['things']:
            file.write(f"\n        ID - {thing['db_id']}, описание поломки: {thing['db_problem_description']};")
    if len(inv_broken) == 0:
        file.write("\n    Нет сломанного инвентаря!")
    # -- inventory --

    # -- bought_plans --
    file.write("\n\n<-- План закупок -->")
    inv_bought = cursor.execute('SELECT * FROM db_bought_inventory').fetchall()
    for plan in inv_bought:
        file.write(f"\n   №{plan['db_id']} {plan['db_name']} ({plan['db_category']}) - по цене {plan['db_price']} руб. "
                   f"в количестве {plan['db_count']} шт. - от {plan['db_producer']};")
    if len(inv_bought) == 0:
        file.write("\n    Нет планируемых закупок!")
    # -- bought_plans --

    file.write("\n\nКонец отчёта.")
    # <---- main_text ---->
    file.close()

    main_text = f"Создан отчёт №{max_index}"
    cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES '
                   '(?, ?, "admins")', (main_text, this_user['db_name'])).fetchone()

    conn.commit()
    conn.close()

    return render_template('reports.html', user=this_user, max_index=max_index,
                           last_text="Отчёт был успешно добавлен!")


# -------------- buttons --------------
@app.route('/add_inventory', methods=['GET', 'POST'])
def add_inventory():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        count = request.form['count']

        # -- errors --
        for one in [name, count]:
            if len(one) == 0:
                return render_template('add_inventory.html', user=this_user,
                                       error="Все поля не должны оставаться пустыми")
        try:
            count = int(count)
        except:
            conn.commit()
            conn.close()
            return render_template('add_inventory.html', user=this_user, error="Невозможное значение количества")

        if count <= 0:
            conn.commit()
            conn.close()
            return render_template('add_inventory.html', user=this_user, error="Невозможное значение количества")
        # -- errors --

        list_id = []
        for i in range(count):
            cursor.execute('INSERT INTO db_inventory (db_type, db_name) VALUES ("free", ?)', (name,))
            list_id.append(cursor.lastrowid)

        main_text = f"Добавленный инвентарь - \"{name}\" ({count} шт.), ID: {', '.join(str(id) for id in list_id)}"
        cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES '
                       '(?, ?, "admins")', (main_text, this_user['db_name'])).fetchone()

        conn.commit()
        conn.close()
        list_id_text = f"Обязательно сохраните ID-номера добавленного инвентаря \"{name}\" ({count} шт.):"
        return render_template('add_inventory.html', user=this_user, list_id_text=list_id_text, list_id=list_id)

    conn.commit()
    conn.close()
    return render_template('add_inventory.html', user=this_user)


repeat_list = []


@app.route('/delete_inventory', methods=['GET', 'POST'])
def delete_inventory():
    global is_logged, this_user, repeat_list

    if not is_logged:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        list_id = request.form['list_id'].split(" ")

        # -- errors --
        if len(list_id) == 0:
            return render_template('delete_inventory.html', user=this_user, delete_list={},
                                   error="Все поля не должны оставаться пустыми")
        for id in list_id:
            try:
                a = int(id)
                id = a
            except:
                return render_template('delete_inventory.html', user=this_user, error="Ошибка ввода ID", delete_list={})

            lenght = len(cursor.execute('SELECT * FROM db_inventory WHERE db_id = ?', (id,)).fetchall())
            if id <= 0 or lenght == 0:
                return render_template('delete_inventory.html', user=this_user, error="Ошибка ввода ID", delete_list={})
        # -- errors --

        delete_list = {'free and broken': [], 'usefull': []}
        for id in list_id:
            thing = cursor.execute('SELECT * FROM db_inventory WHERE db_id = ?', (id,)).fetchone()
            if thing['db_type'] == "usefull":
                delete_list['usefull'].append(thing)
            else:
                delete_list['free and broken'].append(thing)

        repeat_list = list_id

        conn.commit()
        conn.close()
        return render_template('repeat_delete_inventory.html', user=this_user, delete_list=delete_list)

    conn.commit()
    conn.close()
    return render_template('delete_inventory.html', user=this_user, delete_list={})


@app.route('/repeat_delete_inventory')
def repeat_delete_inventory():
    global is_logged, this_user, repeat_list

    if not is_logged:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    delete_list = {'free and broken': [], 'usefull': []}
    for id in repeat_list:
        thing = cursor.execute('SELECT * FROM db_inventory WHERE db_id = ?', (id,)).fetchone()
        if thing['db_type'] == "usefull":
            delete_list['usefull'].append(thing)
        else:
            delete_list['free and broken'].append(thing)

    for id in repeat_list:
        thing = cursor.execute('SELECT * FROM db_inventory WHERE db_id = ?', (id,)).fetchone()
        if thing['db_type'] == "usefull":
            list_id = cursor.execute('SELECT db_id_inventory FROM db_users WHERE db_name = ?',
                                     (thing['db_user'],)).fetchone()['db_id_inventory'].split(" ")
            list_id.remove(str(id))
            if len(list_id) != 0:
                list_id = " ".join(str(id) for id in list_id)
            else:
                list_id = None

            cursor.execute('UPDATE db_users SET db_id_inventory = ? WHERE db_name = ?', (list_id, thing['db_user']))

            main_text = f"От вас был откреплён инвентарь по причине его удаления, ID - {id}"
            cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES '
                           '(?, ?, ?)', (main_text, this_user['db_name'], thing['db_user']))

        cursor.execute('DELETE FROM db_inventory WHERE db_id = ?', (id,))

    main_text = f"Удалённый инвентарь, ID: {', '.join(str(id) for id in repeat_list)}"
    cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES '
                   '(?, ?, "admins")', (main_text, this_user['db_name'])).fetchone()

    conn.commit()
    conn.close()
    repeat_list = []
    return render_template('delete_inventory.html', user=this_user, delete_list=delete_list,
                           delete_text="Вы удалили следующий инвентарь:")


fix_user_name = ""


@app.route('/fix_inventory', methods=['GET', 'POST'])
def fix_inventory():
    global is_logged, this_user, fix_user_name

    if not is_logged:
        return redirect(url_for('index'))

    if request.method == 'POST':
        fix_for_user__name = request.form['user_name']
        inventory_name = request.form['inventory_name']
        inventory_count = request.form['inventory_count']

        # -- errors --
        for one in [fix_for_user__name, inventory_name, inventory_count]:
            if len(one) == 0:
                error = "Все поля не должны оставаться пустыми!"
                return render_template('fix_inventory.html', user=this_user, error=error)

        conn = get_db_connection()
        cursor = conn.cursor()
        fix_for_user = cursor.execute('SELECT * FROM db_users WHERE db_name = ? AND db_user_type = "just_user"',
                                      (fix_for_user__name,)).fetchone()
        if fix_for_user is None:
            error = f"Пользователь {fix_for_user__name} не найден!"
            conn.commit()
            conn.close()
            return render_template('fix_inventory.html', user=this_user, error=error)

        is_inventory = cursor.execute('SELECT db_name from db_inventory WHERE db_name = ?',
                                      (inventory_name,)).fetchone()
        if is_inventory is None:
            error = f"Инвентарь {inventory_name} не найден!"
            conn.commit()
            conn.close()
            return render_template('fix_inventory.html', user=this_user, error=error)

        try:
            inventory_count = int(inventory_count)
        except:
            error = f"Недопустимое значение количества - {inventory_count}!"
            conn.commit()
            conn.close()
            return render_template('fix_inventory.html', user=this_user, error=error)

        if inventory_count <= 0:
            error = f"Недопустимое значение количества - {inventory_count}!"
            conn.commit()
            conn.close()
            return render_template('fix_inventory.html', user=this_user, error=error)
        # -- errors --

        inventory = cursor.execute('SELECT * FROM db_inventory WHERE db_type = "free" AND db_name = ?',
                                   (inventory_name,)).fetchall()

        if len(inventory) == 0:
            conn.commit()
            conn.close()
            last_fix_text = "Не удалось закрепить инвентарь - нет ни одного свободного экземпляра"
            return render_template('fix_inventory.html', user=this_user, last_fix_text=last_fix_text)

        fix_list = []
        c = 0
        for thing in inventory:
            if c == inventory_count:
                break
            fix_list.append(thing['db_id'])
            c += 1
        fix_list_str = " ".join(str(id) for id in fix_list)

        not_enough_count = ""
        if inventory_count - c > 0:
            differ = inventory_count - c
            not_enough_count = (
                f"!! Предупреждение !!\n Пользователю не хватило инвентаря в колличестве {differ} шт.\n "
                f"Остальной инвентарь будет закреплён по списку выше\n")

        conn.commit()
        conn.close()
        fix_user_name = fix_for_user__name
        return render_template('repeat_fix_inventory.html', user=this_user, fix_list_str=fix_list_str,
                               fix_list=fix_list, count=c,
                               inventory_name=inventory_name, user_name=fix_for_user__name,
                               not_enough_count=not_enough_count)

    return render_template('fix_inventory.html', user=this_user)


@app.route('/repeat_fix_inventory<fix_list>')
def repeat_fix_inventory(fix_list):
    global is_logged, this_user, fix_user_name

    if not is_logged:
        return redirect(url_for('index'))

    fix_list = fix_list.split(" ")
    conn = get_db_connection()
    cursor = conn.cursor()

    for id in fix_list:
        cursor.execute('UPDATE db_inventory SET db_type = "usefull", db_user = ? WHERE db_id = ?',
                       (fix_user_name, id))

        last_id = cursor.execute('SELECT db_id_inventory FROM db_users WHERE db_name = ?',
                                 (fix_user_name,)).fetchone()['db_id_inventory']
        if last_id is not None:
            new_id = last_id + " " + id
        else:
            new_id = id
        cursor.execute('UPDATE db_users SET db_id_inventory = ? WHERE db_name = ?', (new_id, fix_user_name))

    main_text = f"За вами был закреплён инвентарь, ID: " \
                f"{', '.join(str(id) for id in fix_list)}"
    cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES '
                   '(?, ?, ?)', (main_text, this_user['db_name'], fix_user_name))

    main_text = f"За пользователем {fix_user_name} был закреплён инвентарь, ID: " \
                f"{', '.join(str(id) for id in fix_list)}"
    cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES '
                   '(?, ?, "admins")', (main_text, this_user['db_name']))
    conn.commit()
    conn.close()
    fix_user_name = ""
    return render_template('fix_inventory.html', user=this_user, last_fix_text="Инвентарь был успешно закреплён!")


@app.route('/replace_to_broken_inventory', methods=['GET', 'POST'])
def replace_to_broken_inventory():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    if request.method == 'POST':
        id_inventory = request.form['id_inventory']
        broken_description = request.form['broken_description']

        # -- errors --
        for one in [id_inventory]:
            if len(one) == 0:
                error = "Поле с ID должно быть заполненно!"
                return render_template('replace_to_broken_inventory.html', user=this_user, error=error)

        try:
            id_inventory = int(id_inventory)
        except:
            error = f"Недопустимое значение ID - {id_inventory}!"
            return render_template('replace_to_broken_inventory.html', user=this_user, error=error)

        conn = get_db_connection()
        cursor = conn.cursor()

        thing = cursor.execute('SELECT * FROM db_inventory WHERE db_id = ?', (id_inventory,)).fetchone()
        if thing is None:
            error = f"Инвентарь с ID - {id_inventory} не найден!"
            conn.commit()
            conn.close()
            return render_template('replace_to_broken_inventory.html', user=this_user, error=error)

        if thing['db_type'] == "broken":
            error = f"Инвентарь с ID - {id_inventory} уже находится в сломанном!"
            conn.commit()
            conn.close()
            return render_template('replace_to_broken_inventory.html', user=this_user, error=error)
        # -- errors --

        if thing['db_type'] == "usefull":
            list_id = cursor.execute('SELECT db_id_inventory FROM db_users WHERE db_name = ?',
                                     (thing['db_user'],)).fetchone()['db_id_inventory'].split(" ")
            list_id.remove(str(id_inventory))
            if len(list_id) != 0:
                list_id_new = " ".join(id for id in list_id)
            else:
                list_id_new = None

            cursor.execute('UPDATE db_users SET db_id_inventory = ? WHERE db_name = ?', (list_id_new, thing['db_user']))

            main_text = f"От вас был откреплён инвентарь по причине его поломки, ID - {id_inventory}"
            cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES '
                           '(?, ?, ?)', (main_text, this_user['db_name'], thing['db_user']))

        cursor.execute('UPDATE db_inventory SET db_type = "broken", db_user = ?, db_problem_description = ?'
                       'WHERE db_id = ?', (None, broken_description, id_inventory))

        main_text = f"Инвентарь с ID - {id_inventory} был перемещён в сломанный, " \
                    f"\nописание поломки: {broken_description}"
        cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES '
                       '(?, ?, "admins")', (main_text, this_user['db_name']))

        conn.commit()
        conn.close()
        return render_template('replace_to_broken_inventory.html', user=this_user,
                               last_text="Инвентарь был успешно перемещён в сломанный!")

    return render_template('replace_to_broken_inventory.html', user=this_user)


@app.route('/delete_from_broken_inventory', methods=['GET', 'POST'])
def delete_from_broken_inventory():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    if request.method == 'POST':
        list_id = request.form['list_id']

        # -- errors --
        if len(list_id) == 0:
            error = "Поле с ID должно быть заполненно!"
            return render_template('delete_from_broken_inventory.html', user=this_user, error=error)

        conn = get_db_connection()
        cursor = conn.cursor()
        list_id = list_id.split(" ")
        for id in list_id:
            try:
                a = int(id)
                id = a
            except:
                conn.commit()
                conn.close()
                return render_template('delete_from_broken_inventory.html', user=this_user, error="Ошибка ввода ID")

            if id <= 0:
                conn.commit()
                conn.close()
                return render_template('delete_from_broken_inventory.html', user=this_user, error="Ошибка ввода ID")

            thing = cursor.execute('SELECT * FROM db_inventory WHERE db_id = ?', (id,)).fetchone()
            if thing is None:
                error = f"Инвентарь с ID - {id} не найден!"
                conn.commit()
                conn.close()
                return render_template('delete_from_broken_inventory.html', user=this_user, error=error)

            if thing['db_type'] != "broken":
                error = f"Инвентарь с ID - {id} не сломан!"
                conn.commit()
                conn.close()
                return render_template('delete_from_broken_inventory.html', user=this_user, error=error)
        # -- errors --

        for id in list_id:
            cursor.execute('UPDATE db_inventory SET db_type = "free", db_problem_description = ? WHERE db_id = ?',
                           (None, id))

        main_text = f"Инвентарь был перемещён из сломанного в доступный, ID: {', '.join(str(id) for id in list_id)}"
        cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES '
                       '(?, ?, "admins")', (main_text, this_user['db_name']))

        conn.commit()
        conn.close()
        return render_template('delete_from_broken_inventory.html', user=this_user,
                               last_text="Инвентарь был успешно перемещён из сломанного в доступный!")

    return render_template('delete_from_broken_inventory.html', user=this_user)


@app.route('/refix_inventory', methods=['GET', 'POST'])
def refix_inventory():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    if request.method == 'POST':
        list_id = request.form['list_id']
        user_name = request.form['user_name']

        # -- errors --
        for one in [list_id, user_name]:
            if len(one) == 0:
                error = "Все поля должны быть заполнены!"
                return render_template('refix_inventory.html', user=this_user, error=error)

        conn = get_db_connection()
        cursor = conn.cursor()
        list_id = list_id.split(" ")
        for id in list_id:
            try:
                a = int(id)
                id = a
            except:
                conn.commit()
                conn.close()
                return render_template('refix_inventory.html', user=this_user, error="Ошибка ввода ID")

            if id <= 0:
                conn.commit()
                conn.close()
                return render_template('refix_inventory.html', user=this_user, error="Ошибка ввода ID")

            thing = cursor.execute('SELECT * FROM db_inventory WHERE db_id = ?', (id,)).fetchone()
            if thing is None:
                error = f"Инвентарь с ID - {id} не найден!"
                conn.commit()
                conn.close()
                return render_template('refix_inventory.html', user=this_user, error=error)

            if thing['db_type'] != "usefull":
                error = f"Инвентарь с ID - {id} ни за кем не закреплён!"
                conn.commit()
                conn.close()
                return render_template('refix_inventory.html', user=this_user, error=error)

        user = cursor.execute('SELECT * FROM db_users WHERE db_name = ? AND db_user_type = "just_user"',
                              (user_name,)).fetchone()
        if user is None:
            error = f"Пользователь {user_name} не найден!"
            conn.commit()
            conn.close()
            return render_template('refix_inventory.html', user=this_user, error=error)

        user_id_inventory = user['db_id_inventory']
        if user_id_inventory is not None:
            user_id_inventory = user_id_inventory.split(" ")
            for id in list_id:
                if id not in user_id_inventory:
                    error = f"Ивентарь с ID - {id} не закреплён за пользователем {user_name}!"
                    conn.commit()
                    conn.close()
                    return render_template('refix_inventory.html', user=this_user, error=error)
        else:
            error = f"У пользователя {user_name} нет закреплённого инвентаря!"
            conn.commit()
            conn.close()
            return render_template('refix_inventory.html', user=this_user, error=error)
        # -- errors --

        for id in list_id:
            user_id_inventory.remove(str(id))
        if len(user_id_inventory) == 0:
            user_id_inventory = None
        else:
            user_id_inventory = " ".join(id for id in user_id_inventory)
        cursor.execute('UPDATE db_users SET db_id_inventory = ? WHERE db_name = ?', (user_id_inventory, user_name))

        for id in list_id:
            cursor.execute('UPDATE db_inventory SET db_type = "free", db_user = ? WHERE db_id = ?', (None, id))

        main_text = f"От вас был откреплён инвентарь, ID: {', '.join(str(id) for id in list_id)}"
        cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES '
                       '(?, ?, ?)', (main_text, this_user['db_name'], user_name))

        main_text = f"Инвентарь был откреплён от пользователя {user_name}, ID: {', '.join(str(id) for id in list_id)}"
        cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES '
                       '(?, ?, "admins")', (main_text, this_user['db_name']))

        conn.commit()
        conn.close()
        return render_template('refix_inventory.html', user=this_user,
                               last_text="Инвентарь был успешно откреплён! Теперь он доступен другим пользователем!")

    return render_template('refix_inventory.html', user=this_user)


# -------------- buttons --------------


# -------------- just_users --------------
@app.route('/zayavka_from_user', methods=['GET', 'POST'])
def zayavka_from_user():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    if request.method == 'POST':
        name_inventory = request.form['name_inventory']
        count = request.form['count']

        # ---- errors ----
        for one in [name_inventory, count]:
            if len(one) == 0:
                error = "Все поля должны быть заполнены!"
                return render_template('zayavka_from_user.html', user=this_user, error=error)

        try:
            count = int(count)
        except:
            error = "Недопустимое значение количества!"
            return render_template('zayavka_from_user.html', user=this_user, error=error)

        if count <= 0:
            error = "Недопустимое значение количества!"
            return render_template('zayavka_from_user.html', user=this_user, error=error)

        conn = get_db_connection()
        cursor = conn.cursor()

        inventory = cursor.execute('SELECT * FROM db_inventory WHERE db_name = ?', (name_inventory,)).fetchone()
        if inventory is None:
            conn.commit()
            conn.close()
            error = "Инвентарь с таким названием не найден!"
            return render_template('zayavka_from_user.html', user=this_user, error=error)
        # ---- errors ----

        main_for_admin = f"Поступил запрос на получение инвентаря \"{name_inventory}\" в количестве {count} шт."
        cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES '
                       '(?, ?, "admins")', (main_for_admin, this_user['db_name']))

        main_for_user = f"Вы отправили заявку на получение инвентаря \"{name_inventory}\" в количестве {count} шт."
        cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES '
                       '(?, ?, ?)', (main_for_user, "Cистемы Оповещений", this_user['db_name']))
        conn.commit()
        conn.close()
        last_text = "Заявка на получение инвентаря успешно отправлена администраторам на рассмотрение!"
        return render_template('zayavka_from_user.html', user=this_user,
                               last_text=last_text)

    return render_template('zayavka_from_user.html', user=this_user)


@app.route('/message_about_break', methods=['GET', 'POST'])
def message_about_break():
    global is_logged, this_user

    if not is_logged:
        return redirect(url_for('index'))

    if request.method == 'POST':
        id_inventory = request.form['id_inventory']
        problem_description = request.form['problem_description']

        # ---- errors ----
        for one in [id_inventory, problem_description]:
            if len(one) == 0:
                error = "Все поля должны быть заполнены!"
                return render_template('message_about_break.html', user=this_user, error=error)

        try:
            id_inventory = int(id_inventory)
        except:
            error = "Недопустимое значение количества"
            return render_template('message_about_break.html', user=this_user, error=error)

        if id_inventory <= 0:
            error = "Недопустимое значение количества"
            return render_template('message_about_break.html', user=this_user, error=error)

        conn = get_db_connection()
        cursor = conn.cursor()

        inventory = cursor.execute('SELECT * FROM db_inventory WHERE db_id= ?', (id_inventory,)).fetchone()
        if inventory is None:
            conn.commit()
            conn.close()
            error = "Инвентарь с таким ID не найден"
            return render_template('message_about_break.html', user=this_user, error=error)
        # ---- errors ----

        main_for_admins = f"Поступило сообщение о поломке инвентаря с ID - {id_inventory}: \n{problem_description}"
        cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES '
                       '(?, ?, "admins")', (main_for_admins, this_user['db_name']))

        main_for_user = f"Вы отправили сообщение о поломке инвентаря с ID - {id_inventory}: \n{problem_description}"
        cursor.execute('INSERT INTO db_notice (db_main, db_sender, db_recipient) VALUES '
                       '(?, ?, ?)', (main_for_user, "Cистемы оповещений", this_user['db_name']))

        conn.commit()
        conn.close()
        return render_template('message_about_break.html', user=this_user,
                               last_text="Сообщение о поломке успешно отправлено администраторам на рассмотрение!")

    return render_template('message_about_break.html', user=this_user)


# -------------- just_users --------------


if __name__ == '__main__':
    app.run()
