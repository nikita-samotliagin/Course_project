import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]
BASE=os.getenv('BASE_URL','http://127.0.0.1:5065')

def run():
    shots=ROOT/'docs/screenshots'
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.getenv('CHROME_PATH',r'C:\Program Files\Google\Chrome\Application\chrome.exe'),headless=True)
        page=browser.new_page(viewport={'width':1500,'height':1120},locale='ru-RU')
        page.add_init_script('''{
            const original=HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext=function(...args){
                const ctx=original.apply(this,args);
                if(args[0]==='2d' && this.id==='revenue-chart' && !ctx.__axisCheck){
                    ctx.__axisCheck=true;ctx.__axisLabels=[];
                    const clear=ctx.clearRect.bind(ctx),text=ctx.fillText.bind(ctx);
                    ctx.clearRect=(...a)=>{ctx.__axisLabels=[];return clear(...a);};
                    ctx.fillText=(value,x,y,...a)=>{if(x===52)ctx.__axisLabels.push(String(value));return text(value,x,y,...a);};
                }
                return ctx;
            };
        }''')
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE+'/login');page.locator('[name=email]').fill('admin@example.test');page.locator('[name=password]').fill('DemoPass2026!');page.get_by_role('button',name='Войти',exact=True).click();page.locator('#revenue-chart').wait_for()
        page.screenshot(path=str(shots/'02_dashboard.png'),full_page=True)
        with page.expect_download() as download:
            page.locator('[data-download="0"]').click()
        download.value.save_as(str(shots/'chart-export.png'))
        assert (shots/'chart-export.png').read_bytes().startswith(b'\x89PNG')
        page.locator('#revenue-chart').hover(position={'x':300,'y':100});page.screenshot(path=str(shots/'03_tooltip.png'),full_page=True)
        page.locator('#filters [name=category_id]').select_option('2');page.get_by_role('button',name='Применить',exact=True).click()
        page.wait_for_function("()=>document.querySelector('#category-chart')&&document.querySelectorAll('.metric strong')[1].textContent!=='126'")
        page.mouse.move(0,0);page.screenshot(path=str(shots/'06_category_filter.png'),full_page=True)
        page.goto(BASE+'/dashboard?date_from=2026-09-01&date_to=2026-09-03');expect(page.locator('.metric').nth(1).locator('strong')).to_have_text('0')
        labels=page.locator('#revenue-chart').evaluate("c=>c.getContext('2d').__axisLabels")
        assert labels==['0','0,25','0,5','0,75','1'],labels
        assert len(set(labels))==5
        page.screenshot(path=str(shots/'08_empty.png'),full_page=True)
        page.goto(BASE+'/dashboard?date_from=2026-09-01&date_to=2026-09-01');expect(page.locator('.metric').nth(1).locator('strong')).to_have_text('0')
        single=page.locator('#revenue-chart').evaluate("c=>c.getContext('2d').__axisLabels")
        assert single==labels,single
        mobile=browser.new_page(viewport={'width':390,'height':844},is_mobile=True)
        mobile.goto(BASE+'/login');mobile.locator('[name=email]').fill('analyst@example.test');mobile.locator('[name=password]').fill('DemoPass2026!');mobile.get_by_role('button',name='Войти',exact=True).click();mobile.locator('#revenue-chart').wait_for()
        assert mobile.evaluate('()=>document.documentElement.scrollWidth<=innerWidth')
        mobile.screenshot(path=str(shots/'09_mobile.png'),full_page=True)
        assert not errors,errors
        browser.close()
    result={'date':'2026-11-06','empty_period_axis_labels':labels,'single_day_axis_labels':single,'labels_unique':True,'mobile_overflow':False,'javascript_errors':errors}
    (ROOT/'docs/chart-axis-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':run()
