import io,sqlite3,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import create_app
from backend.db import get_db,migrate
from backend.analytics import integer,money_to_cents,parse_date
from werkzeug.security import generate_password_hash

@pytest.fixture
def app(tmp_path):
    app=create_app({'TESTING':True,'SECRET_KEY':'test','DATABASE':str(tmp_path/'test.db')})
    with app.app_context():
        migrate();db=get_db()
        with db:
            for name,email,role in [('Админ','admin@example.test','admin'),('Аналитик','analyst@example.test','analyst')]:db.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)',(name,email,generate_password_hash('TestPass2026!'),role))
            db.executemany('INSERT INTO categories(name) VALUES(?)',[('Электроника',),('Дом',)])
            db.executemany('INSERT INTO products(category_id,name,price_cents) VALUES(?,?,?)',[(1,'Товар А',1000),(2,'Товар Б',2500)])
    return app

@pytest.fixture
def client(app):return app.test_client()
def token(c):return {'X-CSRF-Token':c.get('/api/session').json['csrf']}
def login(c,email='admin@example.test'):
    r=c.post('/api/auth/login',json={'email':email,'password':'TestPass2026!'},headers=token(c));assert r.status_code==200
def order(**extra):
    result={'number':'TEST-001','ordered_on':'2026-11-01','customer':'Учебный покупатель','status':'delivered','channel':'web','items':[{'product_id':1,'quantity':2,'unit_price':'10.00'},{'product_id':2,'quantity':1,'unit_price':'25.00'}]};result.update(extra);return result
def create(c,**extra):
    r=c.post('/api/orders',json=order(**extra),headers=token(c));assert r.status_code==201,r.json;return r.json['id']
def known(c):
    create(c)
    create(c,number='TEST-002',ordered_on='2026-11-03',items=[{'product_id':1,'quantity':1,'unit_price':'30.00'}])
    create(c,number='TEST-003',ordered_on='2026-11-02',status='cancelled',items=[{'product_id':2,'quantity':3,'unit_price':'25.00'}])
    create(c,number='TEST-004',ordered_on='2026-11-03',status='returned',items=[{'product_id':1,'quantity':2,'unit_price':'10.00'}])
    create(c,number='TEST-005',ordered_on='2026-11-02',status='paid',items=[{'product_id':1,'quantity':4,'unit_price':'10.00'}])

@pytest.mark.parametrize('value,expected',[('0',0),('1.01',101),('1000000',100000000)])
def test_money_exact(value,expected):assert money_to_cents(value)==expected

@pytest.mark.parametrize('value',['-1','1.001','NaN','Infinity',True,'1000001'])
def test_money_invalid(value):
    with pytest.raises(ValueError):money_to_cents(value)

def test_integer_and_date_boundaries():
    assert integer('1',1)==1
    for value in ('-1','1.2',True):
        with pytest.raises(ValueError):integer(value)
    assert parse_date('2024-02-29').day==29
    with pytest.raises(ValueError):parse_date('2026-02-29')

def test_guest_and_csrf(client):
    assert client.get('/api/dashboard').status_code==401
    assert client.post('/api/auth/login',json={}).status_code==403

def test_registration_does_not_accept_admin(client):
    r=client.post('/api/auth/register',json={'name':'Новый аналитик','email':'new@example.test','password':'PassWord2026','role':'admin'},headers=token(client));assert r.status_code==201
    assert client.get('/api/session').json['user']['role']=='analyst'
    assert client.post('/api/orders',json=order(),headers=token(client)).status_code==403

def test_duplicate_email_and_password(client):
    assert client.post('/api/auth/register',json={'name':'Автор','email':'ADMIN@example.test','password':'Password2026'},headers=token(client)).status_code==409
    assert client.post('/api/auth/register',json={'name':'Автор','email':'a@example.test','password':'123456789012'},headers=token(client)).status_code==400

def test_login_token_rotation_and_logout(client):
    old=token(client);login(client)
    assert client.post('/api/auth/logout',headers=old).status_code==403
    assert client.post('/api/auth/logout',headers=token(client)).status_code==200
    assert client.get('/api/dashboard').status_code==401

def test_role_permissions(client):
    login(client,'analyst@example.test');assert client.get('/api/dashboard').status_code==200
    assert client.get('/api/audit').status_code==403
    assert client.post('/api/orders',json=order(),headers=token(client)).status_code==403

def test_crud_history_and_version(client,app):
    login(client);oid=create(client);assert client.get(f'/api/orders/{oid}').json['version']==1
    assert client.put(f'/api/orders/{oid}',json=order(version=1,status='paid'),headers=token(client)).status_code==200
    assert client.put(f'/api/orders/{oid}',json=order(version=1),headers=token(client)).status_code==409
    assert client.delete(f'/api/orders/{oid}?version=1',headers=token(client)).status_code==409
    assert client.delete(f'/api/orders/{oid}?version=2',headers=token(client)).status_code==200
    assert client.get(f'/api/orders/{oid}').status_code==404
    assert [x['action'] for x in client.get('/api/audit').json['items']]==['delete','update','create']
    with app.app_context():assert get_db().execute('SELECT count(*) FROM order_items').fetchone()[0]==0

def test_exact_dashboard_totals(client):
    login(client);known(client);r=client.get('/api/dashboard?date_from=2026-11-01&date_to=2026-11-03').json
    assert r['summary']=={'orders':5,'delivered_orders':2,'revenue_cents':7500,'average_cents':3750,'units':4}
    assert [x['revenue_cents'] for x in r['daily']]==[4500,0,3000]
    assert sum(x['count'] for x in r['statuses'])==5
    assert sum(x['revenue_cents'] for x in r['categories'])==7500

def test_category_filters_items_not_entire_order(client):
    login(client);known(client);r=client.get('/api/dashboard?category_id=1').json
    assert r['summary']['revenue_cents']==5000
    assert r['summary']['delivered_orders']==2
    assert r['summary']['average_cents']==2500
    r2=client.get('/api/dashboard?category_id=2').json
    assert r2['summary']['revenue_cents']==2500 and r2['summary']['orders']==2

def test_status_and_date_filters(client):
    login(client);known(client)
    assert client.get('/api/dashboard?status=returned').json['summary']['revenue_cents']==0
    assert client.get('/api/dashboard?date_from=2026-11-01&date_to=2026-11-01').json['summary']['revenue_cents']==4500
    assert client.get('/api/dashboard?channel=phone').json['summary']['orders']==0

@pytest.mark.parametrize('query',['date_from=2026-12-01&date_to=2026-11-01','date_from=2020-01-01&date_to=2026-11-01','category_id=999','status=xxx','channel=xxx','date_from=no'])
def test_invalid_filters(client,query):
    login(client);assert client.get('/api/dashboard?'+query).status_code==400

def test_empty_and_zero_series(client):
    login(client);r=client.get('/api/dashboard?date_from=2026-11-01&date_to=2026-11-03').json
    assert r['summary']['orders']==0 and r['summary']['average_cents']==0
    assert len(r['daily'])==3 and not r['categories']

    assert client.get('/api/dashboard?date_from=0001-01-01&date_to=0001-01-01').json['summary']['orders']==0

@pytest.mark.parametrize('change',[{'items':[]},{'status':'xxx'},{'channel':'xxx'},{'ordered_on':'2026-02-29'},{'number':'x'},{'items':[{'product_id':999,'quantity':1,'unit_price':'1'}]},{'items':[{'product_id':1,'quantity':0,'unit_price':'1'}]}])
def test_order_validation(client,change):
    login(client);assert client.post('/api/orders',json=order(**change),headers=token(client)).status_code==400

def test_duplicate_number_and_items(client):
    login(client);create(client)
    assert client.post('/api/orders',json=order(),headers=token(client)).status_code==409
    x={'product_id':1,'quantity':1,'unit_price':'1'}
    assert client.post('/api/orders',json=order(number='TST-2',items=[x,x]),headers=token(client)).status_code==400

def test_snapshot_price_and_atomic_invalid_update(client,app):
    login(client);oid=create(client)
    with app.app_context():
        db=get_db()
        with db:db.execute('UPDATE products SET price_cents=99999 WHERE id=1')
    assert client.get('/api/dashboard').json['summary']['revenue_cents']==4500
    assert client.put(f'/api/orders/{oid}',json=order(version=1,items=[]),headers=token(client)).status_code==400
    assert len(client.get(f'/api/orders/{oid}').json['items'])==2

def test_csv_matches_dashboard(client):
    login(client);known(client);r=client.get('/api/export.csv?date_from=2026-11-01&date_to=2026-11-03')
    assert r.status_code==200 and r.mimetype=='text/csv'
    rows=list(__import__('csv').DictReader(io.StringIO(r.data.decode())))
    assert [x['delivered_revenue_rub'] for x in rows]==['45.00','0.00','30.00']

def test_list_pagination_and_category_total(client):
    login(client)
    for i in range(14):create(client,number=f'PAGE-{i}')
    assert len(client.get('/api/orders?page=2').json['items'])==2
    assert client.get('/api/orders?category_id=1').json['items'][0]['total_cents']==4500

def test_migrations_constraints_and_security_headers(app,client):
    with app.app_context():
        migrate();assert get_db().execute('SELECT count(*) FROM schema_migrations').fetchone()[0]==1
        with pytest.raises(sqlite3.IntegrityError):
            with get_db():get_db().execute('INSERT INTO order_items(order_id,product_id,quantity,unit_price_cents) VALUES(999,1,1,1)')
    r=client.get('/');assert r.headers['X-Frame-Options']=='DENY' and "script-src 'self'" in r.headers['Content-Security-Policy']
    assert client.get('/api/absent').status_code==404
