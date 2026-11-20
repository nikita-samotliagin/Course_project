import os,secrets
from datetime import timedelta
from pathlib import Path
from flask import Flask,jsonify,render_template,request
from werkzeug.exceptions import HTTPException
from .db import close_db

def create_app(config=None):
    root=Path(__file__).resolve().parent.parent;instance=root/'instance';instance.mkdir(exist_ok=True)
    key=os.environ.get('SECRET_KEY')
    if not key:
        path=instance/'.secret'
        if not path.exists():
            try:
                with path.open('x',encoding='utf-8') as file:file.write(secrets.token_hex(32))
            except FileExistsError:pass
        key=path.read_text(encoding='utf-8').strip()
    app=Flask(__name__,template_folder=str(root/'frontend/templates'),static_folder=str(root/'frontend/static'))
    app.config.update(SECRET_KEY=key,DATABASE=str(instance/'orderpulse.db'),MAX_CONTENT_LENGTH=1024*1024,
        SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE')=='1',PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
    if config:app.config.update(config)
    app.teardown_appcontext(close_db)
    from .routes import bp
    app.register_blueprint(bp)
    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff';response.headers['X-Frame-Options']='DENY';response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response.headers['Cache-Control']='no-store'
        return response
    @app.errorhandler(HTTPException)
    def http_error(exc):
        messages={400:'Проверьте данные запроса.',401:'Войдите в аккаунт.',403:'Недостаточно прав или неверный токен.',404:'Ресурс не найден.',409:'Данные изменились. Обновите список.',413:'Слишком большой запрос.',429:'Повторите попытку позже.'}
        if request.path.startswith('/api/'):return jsonify(error=messages.get(exc.code,'Ошибка запроса.')),exc.code
        return render_template('index.html'),exc.code
    return app
