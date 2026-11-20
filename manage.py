import argparse,os
from backend import create_app
from backend.db import migrate
from backend.seed import seed

def main():
    p=argparse.ArgumentParser(description='Управление учебной системой Пульс заказов');p.add_argument('command',choices=['migrate','seed','run','serve']);p.add_argument('--port',type=int,default=5065);args=p.parse_args()
    app=create_app()
    with app.app_context():
        migrate()
        if args.command=='seed':seed();print('Демонстрационные аккаунты: admin@example.test и analyst@example.test; пароль DemoPass2026!')
    if args.command=='run':app.run(host='127.0.0.1',port=args.port,debug=False)
    if args.command=='serve':
        if len(os.getenv('SECRET_KEY',''))<32:raise SystemExit('Укажите SECRET_KEY длиной от 32 символов.')
        from waitress import serve
        serve(app,host='127.0.0.1',port=args.port,threads=4)
if __name__=='__main__':main()
