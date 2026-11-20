import csv,hmac,io,json,re,secrets,sqlite3,time
from collections import defaultdict,deque
from functools import wraps
from flask import Blueprint,abort,current_app,g,jsonify,render_template,request,session,Response
from werkzeug.security import check_password_hash,generate_password_hash
from .db import get_db
from .analytics import CHANNELS,STATUSES,calculate,filters,integer,money_to_cents,parse_date,selection

bp=Blueprint('main',__name__)
attempts=defaultdict(deque)

@bp.before_app_request
def prepare():
    session.setdefault('csrf',secrets.token_hex(32))
    g.user=get_db().execute('SELECT id,name,email,role FROM users WHERE id=?',(session.get('uid'),)).fetchone()
    if request.path.startswith('/api/') and request.method in ('POST','PUT','DELETE'):
        if not hmac.compare_digest(session['csrf'],request.headers.get('X-CSRF-Token','')):abort(403)

def auth(admin=False):
    def outer(fn):
        @wraps(fn)
        def inner(*args,**kwargs):
            if not g.user:abort(401)
            if admin and g.user['role']!='admin':abort(403)
            return fn(*args,**kwargs)
        return inner
    return outer

def data():
    result=request.get_json(silent=True)
    if not isinstance(result,dict):abort(400)
    return result

def error(message,status=400):return jsonify(error=message),status

@bp.get('/')
@bp.get('/dashboard')
@bp.get('/orders')
@bp.get('/audit')
@bp.get('/login')
@bp.get('/register')
@bp.get('/api-help')
def shell():return render_template('index.html')

@bp.get('/api/session')
def state():return jsonify(user=dict(g.user) if g.user else None,csrf=session['csrf'])

@bp.post('/api/auth/register')
def register():
    v=data();name=str(v.get('name','')).strip();email=str(v.get('email','')).strip().lower();password=str(v.get('password',''))
    if not 2<=len(name)<=80 or len(email)>120 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):return error('Введите имя и корректный email.')
    if not 10<=len(password)<=128 or not re.search(r'[^\W\d_]',password) or not re.search(r'\d',password):return error('Пароль: 10-128 символов, буква и цифра.')
    db=get_db()
    try:
        with db:uid=db.execute('INSERT INTO users(name,email,password_hash) VALUES(?,?,?)',(name,email,generate_password_hash(password))).lastrowid
    except sqlite3.IntegrityError:return error('Email уже зарегистрирован.',409)
    session.clear();session.update(uid=uid,csrf=secrets.token_hex(32));session.permanent=True
    return jsonify(id=uid),201

@bp.post('/api/auth/login')
def login():
    v=data();email=str(v.get('email','')).strip().lower();password=str(v.get('password',''))
    if len(email)>120 or len(password)>128:return error('Неверный email или пароль.',401)
    key=(request.remote_addr,email);queue=attempts[key];now=time.monotonic()
    while queue and queue[0]<now-300:queue.popleft()
    if len(queue)>=10:abort(429)
    queue.append(now);row=get_db().execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
    if not row or not check_password_hash(row['password_hash'],password):return error('Неверный email или пароль.',401)
    attempts.pop(key,None);session.clear();session.update(uid=row['id'],csrf=secrets.token_hex(32));session.permanent=True
    return jsonify(ok=True)

@bp.post('/api/auth/logout')
def logout():session.clear();return jsonify(ok=True)

@bp.get('/api/dictionaries')
@auth()
def dictionaries():
    db=get_db();bounds=db.execute('SELECT min(ordered_on),max(ordered_on) FROM orders').fetchone()
    default=filters({})
    return jsonify(categories=[dict(r) for r in db.execute('SELECT * FROM categories')],products=[dict(r) for r in db.execute('SELECT * FROM products')],statuses=STATUSES,channels=CHANNELS,date_from=default['date_from'],date_to=default['date_to'])

@bp.get('/api/dashboard')
@auth()
def dashboard():
    try:return jsonify(calculate(filters(request.args)))
    except ValueError as exc:return error(str(exc))

@bp.get('/api/orders')
@auth()
def order_list():
    try:f=filters(request.args);page=integer(request.args.get('page',1),1,100000)
    except ValueError as exc:return error(str(exc))
    where,params=selection(f);db=get_db()
    base=' FROM orders o JOIN order_items i ON i.order_id=o.id JOIN products p ON p.id=i.product_id WHERE '+where
    count=db.execute('SELECT count(DISTINCT o.id)'+base,params).fetchone()[0]
    ids=[r[0] for r in db.execute('SELECT DISTINCT o.id'+base+' ORDER BY o.ordered_on DESC,o.id DESC LIMIT 12 OFFSET ?',params+[(page-1)*12])]
    rows=[]
    for oid in ids:
        row=dict(db.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone())
        row['total_cents']=db.execute('SELECT sum(quantity*unit_price_cents) FROM order_items WHERE order_id=?',(oid,)).fetchone()[0]
        rows.append(row)
    return jsonify(items=rows,total=count,pages=(count+11)//12,page=page,filters=f)

@bp.get('/api/orders/<int:oid>')
@auth()
def order_detail(oid):
    db=get_db();row=db.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
    if not row:abort(404)
    result=dict(row);result['items']=[dict(r) for r in db.execute('SELECT i.*,p.name FROM order_items i JOIN products p ON p.id=i.product_id WHERE order_id=?',(oid,))]
    return jsonify(result)

def validate_order(v):
    number=str(v.get('number','')).strip();customer=str(v.get('customer','')).strip()
    if not re.fullmatch(r'[A-Za-z0-9-]{3,24}',number):raise ValueError('Номер: 3-24 латинских буквы, цифры или дефис.')
    if not 2<=len(customer)<=80:raise ValueError('Обозначение покупателя: 2-80 символов.')
    day=parse_date(v.get('ordered_on')).isoformat();channel=v.get('channel');status=v.get('status')
    if channel not in CHANNELS or status not in STATUSES:raise ValueError('Выберите канал и статус.')
    items=v.get('items')
    if not isinstance(items,list) or not 1<=len(items)<=20:raise ValueError('Заказ должен содержать 1-20 позиций.')
    checked=[];seen=set();total=0;db=get_db()
    for item in items:
        if not isinstance(item,dict):raise ValueError('Некорректная позиция заказа.')
        product_id=integer(item.get('product_id'),1);quantity=integer(item.get('quantity'),1,10000)
        if product_id in seen or not db.execute('SELECT 1 FROM products WHERE id=?',(product_id,)).fetchone():raise ValueError('Товар отсутствует или повторяется.')
        seen.add(product_id);price=money_to_cents(item.get('unit_price'));total+=price*quantity
        checked.append((product_id,quantity,price))
    if total>10000000000:raise ValueError('Сумма заказа превышает 100 млн руб.')
    return (number,day,customer,channel,status),checked

def audit(db,action,number,details):
    db.execute('INSERT INTO audit_log(actor_id,action,order_number,details) VALUES(?,?,?,?)',(g.user['id'],action,number,json.dumps(details,ensure_ascii=False)))

@bp.post('/api/orders')
@auth(admin=True)
def create_order():
    try:fields,items=validate_order(data())
    except ValueError as exc:return error(str(exc))
    db=get_db()
    try:
        with db:
            oid=db.execute('INSERT INTO orders(number,ordered_on,customer,channel,status,created_by) VALUES(?,?,?,?,?,?)',fields+(g.user['id'],)).lastrowid
            db.executemany('INSERT INTO order_items(order_id,product_id,quantity,unit_price_cents) VALUES(?,?,?,?)',[(oid,)+i for i in items])
            audit(db,'create',fields[0],{'id':oid,'status':fields[4],'items':len(items)})
    except sqlite3.IntegrityError:return error('Номер заказа уже существует.',409)
    return jsonify(id=oid),201

@bp.put('/api/orders/<int:oid>')
@auth(admin=True)
def update_order(oid):
    v=data()
    try:fields,items=validate_order(v);version=integer(v.get('version'),1)
    except ValueError as exc:return error(str(exc))
    db=get_db();old=db.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
    if not old:abort(404)
    try:
        with db:
            changed=db.execute('UPDATE orders SET number=?,ordered_on=?,customer=?,channel=?,status=?,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE id=? AND version=?',fields+(oid,version))
            if not changed.rowcount:abort(409)
            db.execute('DELETE FROM order_items WHERE order_id=?',(oid,))
            db.executemany('INSERT INTO order_items(order_id,product_id,quantity,unit_price_cents) VALUES(?,?,?,?)',[(oid,)+i for i in items])
            audit(db,'update',fields[0],{'id':oid,'old_status':old['status'],'new_status':fields[4],'old_version':version})
    except sqlite3.IntegrityError:return error('Номер заказа уже существует.',409)
    return jsonify(ok=True)

@bp.delete('/api/orders/<int:oid>')
@auth(admin=True)
def delete_order(oid):
    try:version=integer(request.args.get('version'),1)
    except ValueError as exc:return error(str(exc))
    db=get_db();old=db.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
    if not old:abort(404)
    with db:
        changed=db.execute('DELETE FROM orders WHERE id=? AND version=?',(oid,version))
        if not changed.rowcount:abort(409)
        audit(db,'delete',old['number'],{'id':oid,'status':old['status']})
    return jsonify(ok=True)

@bp.get('/api/audit')
@auth(admin=True)
def audit_list():
    return jsonify(items=[dict(r) for r in get_db().execute('SELECT a.*,u.name actor FROM audit_log a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 200')])

@bp.get('/api/export.csv')
@auth()
def export_csv():
    try:result=calculate(filters(request.args))
    except ValueError as exc:return error(str(exc))
    text=io.StringIO();writer=csv.writer(text,lineterminator='\r\n');writer.writerow(['date','orders','delivered_revenue_rub'])
    for row in result['daily']:writer.writerow([row['date'],row['orders'],f"{row['revenue_cents']/100:.2f}"])
    return Response(text.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename="order-statistics.csv"','Cache-Control':'no-store'})
