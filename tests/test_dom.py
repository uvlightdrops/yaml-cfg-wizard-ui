from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import re
from pathlib import Path
import shutil
import subprocess
import threading
import unittest
from uuid import uuid4

from yaml_cfg_wizard_ui import render_page


class DOMTests(unittest.TestCase):
    def test_real_browser_types_requests_conflicts_errors_and_injection(self):
        chrome = os.environ.get("CHROME") or shutil.which("google-chrome") or shutil.which("chromium")
        if not chrome:
            self.skipTest("Chrome/Chromium required for DOM validation")
        setup = r"""
window.requests = [];
window.responses = [];
window.failNetwork = false;
window.currentSnapshot = {revision:"r1",rows:[
 {path:"text",label:"<img src=x onerror=alert(1)>",description:"</script><script>bad()</script>",overridden:true,override:"<svg onload=bad()>",effective:"<b>effective</b>"},
 {path:"flag",label:"Boolean",description:"",overridden:true,override:false,effective:false},
 {path:"count",label:"Integer",description:"",overridden:true,override:2,effective:2},
 {path:"ratio",label:"Number",description:"",overridden:false,override:null,effective:0.5},
 {path:"optional",label:"Optional",description:"",overridden:true,override:null,effective:null},
 {path:"unknown",label:"Unknown null",description:"",overridden:false,override:null,effective:null},
 {path:"__proto__",label:"Prototype path",description:"",overridden:true,override:"safe",effective:"safe"}
]};
window.fetch = async (url, options) => {
 requests.push({url,options,body:options.body ? JSON.parse(options.body) : null});
 if(failNetwork) { failNetwork=false; throw new Error("private network details"); }
 const response=responses.shift() || {status:200,snapshot:currentSnapshot};
 return {ok:response.status===200,status:response.status,json:async()=>response.snapshot};
};
"""
        checks = r"""
(async()=>{
 const assert=(ok,message)=>{if(!ok)throw new Error(message)};
 const tick=async()=>{for(let i=0;i<8;i++)await Promise.resolve()};
 const forms=()=>[...document.querySelectorAll("#fields form")];
 const submit=async(index,value,type)=>{
   const form=forms()[index], input=form.querySelector("input"), select=form.querySelector("select");
   if(type){select.value=type;select.dispatchEvent(new Event("change"));}
   input.value=value;form.dispatchEvent(new Event("submit",{bubbles:true,cancelable:true}));await tick();
 };
 const reload=async()=>{document.getElementById("reload").click();await tick()};
 try {
 await tick();
 assert(forms().length===7,"all allowlisted rows rendered");
 assert(document.querySelectorAll("img,svg").length===0,"hostile labels and values inert");
 assert(document.querySelector("legend").textContent.includes("<img"),"literal hostile label");
 assert(document.getElementById("editor-title").textContent.includes("</script>"),"hostile config title literal");
 assert(requests[0].url==="/api/editor" && requests[0].options.credentials==="same-origin","configured endpoint cookie auth");
 assert(forms()[5].querySelector("button").disabled,"unknown null not guessed");
 await submit(0,"literal <script>attack</script>");
 let req=requests.at(-1);
 assert(req.options.method==="POST" && req.options.headers["X-CSRF-Token"]==="csrf<&>","CSRF header");
 assert(req.body.revision==="r1" && Object.keys(req.body.changes).length===1 && req.body.changes.text==="literal <script>attack</script>" && req.body.remove.length===0,"one string change");
 assert(document.getElementById("saved").textContent==="Saved; restart required","saved feedback");
 await submit(1,"true");
 assert(requests.at(-1).body.changes.flag===true,"boolean type");
 await submit(2,"12");
 assert(requests.at(-1).body.changes.count===12,"integer type");
 let count=requests.length;
 await submit(2,"1.2");assert(requests.length===count,"invalid integer no request");
 await submit(3,"1.25");
 assert(requests.at(-1).body.changes.ratio===1.25,"number type");
 await submit(4,"","null");
 assert(requests.at(-1).body.changes.optional===null,"null explicit");
 await submit(4,"new","string");
 assert(requests.at(-1).body.changes.optional==="new","null inherited schema string");
 await submit(6,"new");
 assert(Object.hasOwn(requests.at(-1).body.changes,"__proto__"),"prototype path preserved");
 forms()[0].querySelectorAll("button")[1].click();await tick();
 assert(requests.at(-1).body.remove[0]==="text" && Object.keys(requests.at(-1).body.changes).length===0,"remove inherits one field");
 responses.push({status:409});
 await submit(0,"retain draft");
 assert(document.getElementById("error").textContent.includes("Reload explicitly"),"conflict feedback");
 assert(forms()[0].querySelector("input").value==="retain draft","draft retained");
 assert(forms()[0].querySelector("button").disabled,"conflict blocks saving");
 count=requests.length;await submit(0,"must not send");assert(requests.length===count,"no silent retry");
 responses.push({status:403});await reload();
 assert(forms()[0].querySelector("button").disabled,"failed reload retains conflict");
 assert(document.getElementById("error").textContent.includes("CSRF"),"auth CSRF feedback");
 currentSnapshot={...currentSnapshot,revision:"r2"};await reload();
 assert(!forms()[0].querySelector("button").disabled,"explicit reload clears conflict");
 await submit(0,"new revision");assert(requests.at(-1).body.revision==="r2","revision updates only on success");
 for(const code of [401,403,400,422,503]){
   responses.push({status:code});await submit(0,"bad");
   assert(document.getElementById("error").textContent.length>0,"explicit HTTP error "+code);
   assert(requests.at(-1).body.revision==="r2","failure retains revision");
 }
 failNetwork=true;await submit(0,"offline");
 assert(document.getElementById("error").textContent.includes("connectivity"),"network explicit");
 responses.push({status:200,snapshot:{revision:"evil",rows:[{path:"x",effective:{secret:"private"}}]}});
 await submit(0,"invalid response");
 assert(document.getElementById("error").textContent.includes("Invalid snapshot"),"invalid snapshot explicit");
 assert(forms().length===7,"invalid response keeps prior rows");
 await submit(0,"still r2");assert(requests.at(-1).body.revision==="r2","malformed response revision not accepted");
 document.body.dataset.testResult="passed";
 }catch(error){document.body.dataset.testResult="failed: "+error.message}
})();
"""
        page = render_page(endpoint="/api/editor", csrf_token="csrf<&>",
                           title="Hostile </script><img src=x>", saved_message="Saved; restart required",
                           fields={"optional": {"type": ["string", "null"]}, "ratio": {"type": "number"}})
        setup = setup.replace("</script>", r"<\/script>")
        checks = checks.replace("</script>", r"<\/script>")
        page = page.replace('<script nonce="">', f"<script>{setup}</script><script>")
        page = page.replace("</body>", f"<script>{checks}</script></body>")

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(page.encode())

            def log_message(self, *args):
                pass

        root = Path(__file__).resolve().parents[1] / ".validation" / ("b" + uuid4().hex[:6])
        root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, root)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(
                [chrome, "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                 "--no-first-run", "--no-default-browser-check",
                 f"--user-data-dir={root / 'profile'}", f"--crash-dumps-dir={root}",
                 "--virtual-time-budget=8000", "--dump-dom", f"http://127.0.0.1:{server.server_port}/"],
                capture_output=True, text=True, timeout=30,
                env={**os.environ, "TMPDIR": str(root)},
            )
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            outcome = re.search(r'data-test-result="([^"]*)"', result.stdout)
            self.assertIsNotNone(outcome, "Browser harness did not finish")
            self.assertEqual(outcome.group(1), "passed")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
