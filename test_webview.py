import webview
from typing import Any
class API:
    def test(self, val: Any = None):
        print('Success:', val)
api = API()
window = webview.create_window('Test', html='<script>window.addEventListener(\"pywebviewready\", () => pywebview.api.test(\"all\").then(()=>pywebview.api.test(2)).then(()=>pywebview.api.test(\"favorites\")).then(()=>setTimeout(()=>window.close(), 100)))</script>', js_api=api)
webview.start()
