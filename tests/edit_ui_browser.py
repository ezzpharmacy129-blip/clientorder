"""Run manually: python tests/edit_ui_browser.py (requires playwright + Chromium).
Uses the actual template/assets, intercepted synthetic APIs, and no live services.
"""
import copy
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
env = Environment(loader=FileSystemLoader(ROOT/'templates'))
html = env.get_template('index.html').render(settings={}, app_version='test', csrf_token=lambda:'test-csrf',
    url_for=lambda endpoint, filename='': '/static/'+filename)
order_template = {'Order_ID':'ORD-1','Customer_Name':'عميل تجريبي','Phone':'966500000001','Order_Date':'2026-10-01','Notes':'ملاحظة',
    'Status':'متوفر - يحتاج اتصال','Contact_Status':'لم يتم التواصل','Quantity':3,
    'Items':[{'Item_ID':'ITEM-1','Product_Name':'المنتج الأول','Quantity':2,'Image_Path':'sample.png','Availability_Status':'متوفر','Available_Price':'20'},
             {'Item_ID':'ITEM-2','Product_Name':'المنتج الثاني','Quantity':1,'Image_Path':'','Availability_Status':'بانتظار التوفر'}]}

def run(browser, width):
    page = browser.new_page(viewport={'width':width,'height':844})
    order = copy.deepcopy(order_template)
    writes, reads, errors = [], [], []
    pharmacy = [dict(shortage_id='PS-1', product_name='نقص حالي', quantity=2,note='ملاحظة النقص',status='pending',created_at='2026-10-01'),
                dict(shortage_id='PS-2', product_name='نقص متوفر', quantity=3,note='متوفر',status='available',created_at='2026-10-01')]
    page.on('pageerror',lambda e:errors.append(str(e)))
    fail_next = [False]
    def route(r):
        req = r.request; path = urlparse(req.url).path
        if urlparse(req.url).hostname != 'edit.test': return r.fulfill(status=204)
        if path == '/': return r.fulfill(body=html,content_type='text/html')
        if path.startswith('/static/'):
            file = ROOT/path.lstrip('/')
            return r.fulfill(body=file.read_bytes(),content_type=mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
        if path.startswith('/uploads/'):
            return r.fulfill(body='<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50"><rect width="50" height="50" fill="green"/></svg>',content_type='image/svg+xml')
        data = {}
        if req.method != 'GET':
            assert req.headers.get('x-csrf-token') == 'test-csrf'
            payload = req.post_data_json
            writes.append((path,req.method,payload))
            if fail_next[0]:
                fail_next[0] = False
                return r.fulfill(status=400,json={'error':'خطأ تجريبي'})
            if path == '/api/orders/ORD-1':
                assert req.method == 'PUT'
                assert set(payload) == {'customer_name','phone','order_date','notes','products','deleted_item_ids'}
                for key in ('Customer_Name','Phone','Order_Date','Notes'): order[key]=payload[key.lower()]
                old = {i['Item_ID']:i for i in order['Items']}
                order['Items'] = [{**old.get(p.get('item_id'), {'Item_ID':'ITEM-NEW'}), 'Product_Name':p['product_name'],'Quantity':p['quantity']} for p in payload['products']]
                data = {'order':order}
            elif path.startswith('/api/pharmacy-shortages/'):
                assert req.method == 'PUT'
                assert set(payload) == {'product_name','quantity','note'}
                next(p for p in pharmacy if path.endswith(p['shortage_id'])).update(payload)
            else: raise AssertionError(f'Unexpected mutation {path}')
        else:
            reads.append(path)
            if path == '/api/orders/ORD-1': data = {'order':order,'activity_log':[],'undo':{'available':False}}
            elif path == '/api/orders': data = {'orders':[order],'count':1,'pages':1}
            elif path == '/api/shortages': data = {'pharmacy':[pharmacy[0]],'pharmacy_available':[pharmacy[1]],'customer':[{'order_id':'ORD-1','product_name':'المنتج الأول','quantity':2}]}
            elif path == '/api/dashboard': data = {'date':'2026-10-06','total':1,'available':1,'awaiting_reply':0,'overdue':0}
        r.fulfill(json=data)
    page.route('**/*',route)
    page.goto('https://edit.test/')
    # Existing cancelled_orders.js references a removed dashboard global on main.
    # Record that startup failure separately; every edit operation below must be error-free.
    assert errors in ([], ['dashboardFilterOrders is not defined']), errors
    if errors: print('BASELINE startup error:', errors[0])
    errors.clear()
    page.locator('[data-view="orders"]').click()
    edit = page.locator('#orders-table-body .edit-order-btn')
    expect(edit).to_be_visible()
    if width == 390:
        assert edit.bounding_box()['x'] >= 0
        assert edit.bounding_box()['x']+edit.bounding_box()['width'] <= width
    edit.click()
    modal = page.locator('#order-edit-modal')
    expect(modal).to_be_visible()
    expect(modal.locator('h3')).to_have_text('تعديل الطلب #ORD-1')
    expect(modal.locator('img')).to_have_count(1)
    assert modal.locator('.modal').evaluate('(e)=>e.scrollWidth<=e.clientWidth')
    for field in modal.locator('input,textarea').all():
        box = field.bounding_box(); assert box['x'] >= 0 and box['x']+box['width'] <= width
    # Closing and reopening discards edits and deletion, without any API mutation.
    modal.locator('#edit-customer').fill('discard')
    modal.locator('.edit-remove-item').last.click()
    modal.locator('[data-edit-close]').first.click()
    assert writes == []
    edit.click()
    expect(modal.locator('#edit-customer')).to_have_value('عميل تجريبي')
    expect(modal.locator('.order-edit-item')).to_have_count(2)
    modal.locator('#edit-customer').fill('عميل معدل')
    modal.locator('.edit-product-name').first.fill('منتج معدل')
    modal.locator('.edit-product-quantity').first.fill('4')
    modal.locator('.edit-remove-item').last.click()
    modal.locator('#order-edit-add').click()
    modal.locator('.edit-product-name').last.fill('منتج جديد')
    if os.environ.get('EZZ_UI_SCREENSHOTS'):
        out = Path(os.environ['EZZ_UI_SCREENSHOTS']); out.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(out/f'order-edit-{width}.png'))
    fail_next[0] = True
    modal.locator('[type="submit"]').click()
    expect(modal).to_be_visible()
    expect(modal.locator('[type="submit"]')).to_be_enabled()
    before = len(reads)
    modal.locator('[type="submit"]').click()
    expect(modal).to_be_hidden()
    page.wait_for_function("document.querySelector('#orders-table-body').textContent.includes('عميل معدل')")
    assert '/api/dashboard' in reads[before:] and '/api/orders' in reads[before:]
    payload = writes[-1][2]
    assert payload['deleted_item_ids']==['ITEM-2']
    assert payload['products'][0]['item_id']=='ITEM-1' and 'item_id' not in payload['products'][1]
    assert order['Items'][0]['Image_Path']=='sample.png'
    # Details entry point, refresh on save, and empty-order guard.
    page.locator('#orders-table-body .details-btn').click()
    page.locator('#order-modal .modal-edit').click()
    modal.locator('#edit-notes').fill('updated note')
    modal.locator('[type="submit"]').click()
    expect(page.locator('#modal-body')).to_contain_text('updated note')
    page.locator('#order-modal .modal-edit').click()
    expect(modal).to_be_visible()
    while modal.locator('.edit-remove-item').count(): modal.locator('.edit-remove-item').first.click()
    count = len(writes)
    modal.locator('[type="submit"]').click()
    expect(modal).to_be_visible()
    assert len(writes)==count
    modal.locator('[data-edit-close]').first.click()
    page.locator('#modal-close-btn').click()
    # Existing pharmacy modal remains the one implementation for every filter.
    page.locator('[data-view="shortages"]').click()
    for view, sid in [('pharmacy','PS-1'),('pharmacy_available','PS-2'),('all','PS-2')]:
        page.locator(f'[data-shortages-view="{view}"]').click()
        button = page.locator(f'.ps-edit[data-id="{sid}"]')
        expect(button).to_be_visible()
        button.click()
        ps = page.locator('#pharmacy-shortage-modal')
        expect(ps.locator('h3')).to_have_text('تعديل نقص الصيدلية')
        expect(ps.locator('[type="submit"]')).to_have_text('حفظ التعديلات')
        ps.locator('[name="product_name"]').fill('نقص معدل')
        ps.locator('[type="submit"]').click()
        expect(ps).to_be_hidden()
        expect(button).to_be_visible()
    page.locator('[data-shortages-view="customer"]').click()
    page.locator('.ps-order-edit').click()
    expect(modal).to_be_visible()
    expect(modal.locator('h3')).to_have_text('تعديل الطلب #ORD-1')
    modal.locator('[data-edit-close]').first.click()
    page.locator('#add-pharmacy-shortage-btn').click()
    expect(page.locator('#pharmacy-shortage-modal h3')).to_have_text('إضافة نقص صيدلية')
    expect(page.locator('#pharmacy-shortage-form [type="submit"]')).to_have_text('حفظ النقص')
    assert not errors, errors
    page.close()
    print(f'PASS {width}px: entry points, payload identity, cancellation, errors, empty guard, refresh, pharmacy filters, customer routing, CSRF, layout')

with sync_playwright() as p:
    options = {'headless':True}
    if os.environ.get('EZZ_TEST_BROWSER'): options['executable_path']=os.environ['EZZ_TEST_BROWSER']
    browser = p.chromium.launch(**options)
    for width in (1440,390): run(browser,width)
    browser.close()
