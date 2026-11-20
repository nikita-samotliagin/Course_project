from datetime import date,timedelta
from werkzeug.security import generate_password_hash
from .db import get_db

def seed():
    db=get_db()
    if db.execute('SELECT 1 FROM users').fetchone():raise ValueError('В базе уже есть пользователи. Данные не изменены.')
    with db:
        for name,email,role in [('Администратор','admin@example.test','admin'),('Аналитик','analyst@example.test','analyst')]:
            db.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)',(name,email,generate_password_hash('DemoPass2026!'),role))
        db.executemany('INSERT INTO categories(name) VALUES(?)',[(x,) for x in ['Электроника','Товары для дома','Спорт','Книги']])
        products=[(1,'Беспроводные наушники',649000),(1,'Компактная клавиатура',389000),(1,'Настольная акустика',799000),(2,'Лампа для рабочего стола',249000),(2,'Органайзер',129000),(3,'Коврик для тренировок',189000),(3,'Спортивный рюкзак',329000),(4,'Книга по дизайну',219000),(4,'Практикум по программированию',289000)]
        db.executemany('INSERT INTO products(category_id,name,price_cents) VALUES(?,?,?)',products)
        statuses=['delivered','delivered','delivered','paid','shipped','new','cancelled','returned','delivered','delivered']
        for day in range(36):
            for k in range(2+day%4):
                n=day*10+k;status=statuses[(day+k)%len(statuses)];pid=(day+k)%len(products)+1
                oid=db.execute('INSERT INTO orders(number,ordered_on,customer,channel,status,created_by) VALUES(?,?,?,?,?,1)',(f'DEMO-{1000+n}',(date(2026,10,1)+timedelta(days=day)).isoformat(),f'Учебный покупатель {n+1}',['web','web','phone','partner'][(day+k)%4],status)).lastrowid
                db.execute('INSERT INTO order_items(order_id,product_id,quantity,unit_price_cents) VALUES(?,?,?,?)',(oid,pid,1+(k%3),products[pid-1][2]))
                if k%3==0:
                    second=pid%len(products)+1
                    db.execute('INSERT INTO order_items(order_id,product_id,quantity,unit_price_cents) VALUES(?,?,1,?)',(oid,second,products[second-1][2]))
