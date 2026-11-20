import csv,io,json,os,statistics,time
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1];SHOTS=ROOT/'docs/screenshots';SHOTS.mkdir(parents=True,exist_ok=True)
BASE=os.getenv('BASE_URL','http://127.0.0.1:5065')

def run():
    checks=[];errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.getenv('CHROME_PATH',r'C:\Program Files\Google\Chrome\Application\chrome.exe'),headless=True)
        context=browser.new_context(viewport={'width':1500,'height':1120},locale='ru-RU',accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE+'/login');page.locator('#auth-form').wait_for();page.screenshot(path=str(SHOTS/'01_login.png'),full_page=True)
        page.locator('[name=email]').fill('admin@example.test');page.locator('[name=password]').fill('DemoPass2026!');page.get_by_role('button',name='Войти',exact=True).click();page.locator('#revenue-chart').wait_for();expect(page.locator('canvas')).to_have_count(3)
        painted=page.locator('#revenue-chart').evaluate('(c)=>{let a=c.getContext("2d").getImageData(0,0,c.width,c.height).data,n=0;for(let i=0;i<a.length;i+=4)if(a[i]<220&&a[i+1]<220)n++;return n;}')
        assert painted>100;checks.append('Вход администратора и фактическая отрисовка трёх canvas')
        baseline=page.evaluate('async()=>await (await fetch("/api/dashboard")).json()')
        page.screenshot(path=str(SHOTS/'02_dashboard.png'),full_page=True)
        page.locator('#revenue-chart').hover(position={'x':300,'y':100});page.screenshot(path=str(SHOTS/'03_tooltip.png'),full_page=True)
        with page.expect_download() as wait:page.locator('[data-download="0"]').click()
        download=wait.value;download.save_as(str(SHOTS/'chart-export.png'));assert (SHOTS/'chart-export.png').read_bytes().startswith(b'\x89PNG')
        checks.append('Экспорт графика в PNG')
        with page.expect_download() as wait:page.locator('#export-csv').click()
        path=wait.value.path();rows=list(csv.DictReader(io.StringIO(Path(path).read_text(encoding='utf-8'))));assert len(rows)==36
        checks.append('Выгрузка дневной статистики CSV')
        page.evaluate('()=>window.__pulseMark=42');page.locator('nav a[href="/orders"]').click();page.locator('.data-table tbody tr').first.wait_for();assert page.evaluate('()=>window.__pulseMark')==42
        checks.append('Переход SPA без перезагрузки документа');page.screenshot(path=str(SHOTS/'04_orders.png'),full_page=True)
        page.locator('#new-order').click();form=page.locator('#order-form');number='WEB-'+uuid4().hex[:8]
        form.locator('[name=number]').fill(number);form.locator('[name=ordered_on]').fill('2026-11-05');form.locator('[name=customer]').fill('Учебный покупатель проверки');form.locator('[name=status]').select_option('delivered');form.locator('[name=channel]').select_option('web')
        line=page.locator('.order-line').first;line.locator('[name=product_id]').select_option('1');line.locator('[name=quantity]').fill('2');line.locator('[name=unit_price]').fill('1000.25');page.locator('#add-line').click();line=page.locator('.order-line').nth(1);line.locator('[name=product_id]').select_option('4');line.locator('[name=quantity]').fill('1');line.locator('[name=unit_price]').fill('500.00')
        page.screenshot(path=str(SHOTS/'05_editor.png'),full_page=True);page.locator('#save-order').click();expect(page.locator('#order-dialog')).not_to_be_visible();page.get_by_text(number,exact=True).wait_for();checks.append('Создание заказа с двумя категориями и точными копейками')
        page.locator('nav a[href="/dashboard"]').click();page.locator('#revenue-chart').wait_for();after=page.evaluate('async()=>await (await fetch("/api/dashboard")).json()');assert after['summary']['revenue_cents']==baseline['summary']['revenue_cents']+250050
        checks.append('Пересчёт показателя после создания заказа')
        page.locator('#filters [name=category_id]').select_option('2');page.get_by_role('button',name='Применить',exact=True).click();expect(page.locator('#category-chart')).to_be_visible();page.wait_for_timeout(200);page.screenshot(path=str(SHOTS/'06_category_filter.png'),full_page=True)
        checks.append('Фильтрация статистики по категории')
        page.locator('nav a[href="/orders"]').click();page.get_by_text(number,exact=True).wait_for();row=page.locator('tbody tr').filter(has_text=number);row.get_by_role('button',name='Изменить').click();page.locator('#order-form [name=status]').select_option('cancelled');page.locator('#save-order').click();expect(page.locator('#order-dialog')).not_to_be_visible();expect(page.locator('tbody tr').filter(has_text=number)).to_contain_text('Отменён');checks.append('Изменение статуса заказа')
        result=page.evaluate('async()=>await (await fetch("/api/dashboard")).json()');assert result['summary']['revenue_cents']==baseline['summary']['revenue_cents'];checks.append('Исключение отменённого заказа из суммы выполненных')
        page.once('dialog',lambda d:d.accept());page.locator('tbody tr').filter(has_text=number).get_by_role('button',name='Удалить').click();expect(page.get_by_text(number,exact=True)).to_have_count(0);checks.append('Удаление заказа')
        page.locator('nav a[href="/audit"]').click();page.locator('.audit-record').first.wait_for();page.screenshot(path=str(SHOTS/'07_audit.png'),full_page=True);assert len(page.locator('.audit-record').all())>=3;checks.append('Журнал создания, изменения и удаления')
        page.locator('nav a[href="/dashboard"]').click();page.locator('#filters [name=date_from]').fill('2026-09-01');page.locator('#filters [name=date_to]').fill('2026-09-03');page.get_by_role('button',name='Применить',exact=True).click();expect(page.locator('.metric').nth(1).locator('strong')).to_have_text('0');page.screenshot(path=str(SHOTS/'08_empty.png'),full_page=True);checks.append('Пустая выборка и нулевой график')
        mobile=browser.new_context(viewport={'width':390,'height':844},is_mobile=True);mp=mobile.new_page();mp.goto(BASE+'/login');mp.locator('[name=email]').fill('analyst@example.test');mp.locator('[name=password]').fill('DemoPass2026!');mp.get_by_role('button',name='Войти',exact=True).click();mp.locator('#revenue-chart').wait_for();assert mp.evaluate('()=>document.documentElement.scrollWidth<=innerWidth');mp.screenshot(path=str(SHOTS/'09_mobile.png'),full_page=True);checks.append('Мобильная аналитика без переполнения страницы')
        mp.locator('nav a[href="/orders"]').click();mp.locator('.data-table').wait_for();expect(mp.locator('#new-order')).to_have_count(0);assert mp.evaluate('async()=>{const s=await(await fetch("/api/session")).json();const r=await fetch("/api/orders",{method:"POST",headers:{"X-CSRF-Token":s.csrf,"Content-Type":"application/json"},body:"{}"});return r.status;}')==403;checks.append('Запрет изменения заказов аналитику в интерфейсе и API')
        page.goto(BASE+'/register');page.locator('[name=name]').fill('Новый аналитик');page.locator('[name=email]').fill('check-'+uuid4().hex[:8]+'@example.test');page.locator('[name=password]').fill('NewAccount2026!');page.get_by_role('button',name='Зарегистрироваться',exact=True).click();page.locator('#revenue-chart').wait_for();expect(page.locator('#role-label')).to_have_text('Аналитик');checks.append('Регистрация аккаунта с ролью аналитика')
        assert not errors,errors
        timings=[]
        for _ in range(40):
            t=time.perf_counter();page.evaluate('async()=>{const r=await fetch("/api/dashboard");await r.json();return r.status;}');timings.append((time.perf_counter()-t)*1000)
        browser.close()
    result={'browser':'Google Chrome, headless','desktop':'1500x1120','mobile':'390x844','checks':checks,'page_errors':errors,'canvas_nonwhite_pixels':painted,'performance':{'requests':40,'mean_ms':round(statistics.mean(timings),2),'p95_ms':round(sorted(timings)[37],2),'method':'Последовательный запрос dashboard через браузер, включая fetch, JSON и управление браузером; локальный сервер, демонстрационная БД'}}
    (ROOT/'docs/browser-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':run()
