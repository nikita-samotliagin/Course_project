from datetime import date,timedelta
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from flask import request
from .db import get_db

STATUSES={'new':'Новый','paid':'Оплачен','shipped':'Отправлен','delivered':'Выполнен','cancelled':'Отменён','returned':'Возврат'}
CHANNELS={'web':'Сайт','phone':'Телефон','partner':'Партнёр'}

def integer(value,low=0,high=100000000):
    if isinstance(value,bool) or not str(value).isascii() or not str(value).isdigit():
        raise ValueError('Ожидается целое неотрицательное число.')
    number=int(value)
    if not low<=number<=high:raise ValueError('Число вне допустимых границ.')
    return number

def money_to_cents(value):
    try:
        amount=Decimal(str(value))
        if not amount.is_finite() or amount<0 or amount>1000000 or amount.as_tuple().exponent < -2:
            raise ValueError('Цена: от 0 до 1000000 руб., не более двух знаков после запятой.')
        return int(amount*100)
    except (InvalidOperation,TypeError):raise ValueError('Некорректная цена.')

def parse_date(value):
    try:
        if not isinstance(value,str) or len(value)!=10:raise ValueError()
        parsed=date.fromisoformat(value)
        if parsed.isoformat()!=value:raise ValueError()
        return parsed
    except (ValueError,TypeError):raise ValueError('Дата должна иметь формат ГГГГ-ММ-ДД.')

def filters(args):
    db=get_db();bounds=db.execute('SELECT min(ordered_on),max(ordered_on) FROM orders').fetchone()
    end=args.get('date_to') or bounds[1] or date.today().isoformat()
    end_day=parse_date(end)
    earliest=max(parse_date(bounds[0]),date.fromordinal(max(1,end_day.toordinal()-365))).isoformat() if bounds[0] else date.fromordinal(max(1,end_day.toordinal()-29)).isoformat()
    start=args.get('date_from') or earliest
    a,b=parse_date(start),parse_date(end)
    if a>b or (b-a).days>365:raise ValueError('Выберите период от 1 до 366 дней.')
    result={'date_from':start,'date_to':end,'category_id':None,'channel':args.get('channel',''),'status':args.get('status','')}
    if args.get('category_id'):
        result['category_id']=integer(args['category_id'],1)
        if not db.execute('SELECT 1 FROM categories WHERE id=?',(result['category_id'],)).fetchone():raise ValueError('Категория не найдена.')
    if result['channel'] and result['channel'] not in CHANNELS:raise ValueError('Неизвестный канал.')
    if result['status'] and result['status'] not in STATUSES:raise ValueError('Неизвестный статус.')
    return result

def selection(f):
    where=['o.ordered_on BETWEEN ? AND ?'];params=[f['date_from'],f['date_to']]
    for key in ('channel','status'):
        if f[key]:where.append('o.'+key+'=?');params.append(f[key])
    if f['category_id']:where.append('p.category_id=?');params.append(f['category_id'])
    return ' AND '.join(where),params

def calculate(f):
    where,params=selection(f)
    rows=get_db().execute('SELECT o.id,o.ordered_on,o.status,i.quantity,i.unit_price_cents,p.category_id,c.name category,p.name product FROM orders o JOIN order_items i ON i.order_id=o.id JOIN products p ON p.id=i.product_id JOIN categories c ON c.id=p.category_id WHERE '+where+' ORDER BY o.ordered_on,o.id',params).fetchall()
    a,b=parse_date(f['date_from']),parse_date(f['date_to'])
    daily={(a+timedelta(days=k)).isoformat():{'revenue_cents':0,'orders':set()} for k in range((b-a).days+1)}
    categories={};states={s:set() for s in STATUSES};orders=set();delivered=set();revenue=0;units=0
    for row in rows:
        orders.add(row['id']);states[row['status']].add(row['id']);daily[row['ordered_on']]['orders'].add(row['id'])
        if row['status']=='delivered':
            amount=row['quantity']*row['unit_price_cents'];revenue+=amount;units+=row['quantity'];delivered.add(row['id'])
            daily[row['ordered_on']]['revenue_cents']+=amount
            categories[row['category']]=categories.get(row['category'],0)+amount
    average=int((Decimal(revenue)/len(delivered)).quantize(Decimal('1'),rounding=ROUND_HALF_UP)) if delivered else 0
    return {'filters':f,'summary':{'orders':len(orders),'delivered_orders':len(delivered),'revenue_cents':revenue,'average_cents':average,'units':units},
            'daily':[{'date':day,'revenue_cents':value['revenue_cents'],'orders':len(value['orders'])} for day,value in daily.items()],
            'categories':[{'name':name,'revenue_cents':amount} for name,amount in sorted(categories.items(),key=lambda pair:pair[1],reverse=True)],
            'statuses':[{'key':s,'name':label,'count':len(states[s])} for s,label in STATUSES.items()]}
