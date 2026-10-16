
import os,sqlite3,json,secrets,hashlib,csv,io,time
from datetime import datetime,timezone
from functools import wraps
from flask import Flask,request,session,redirect,url_for,render_template_string,abort,Response,flash
from werkzeug.security import check_password_hash,generate_password_hash

BASE=os.path.dirname(__file__)
DB=os.environ.get("IHC_DB_PATH",os.path.join(BASE,"ihc.db"))
os.makedirs(os.path.dirname(os.path.abspath(DB)),exist_ok=True)
ADMIN=os.environ.get("IHC_ADMIN_PASSWORD")
SECRET=os.environ.get("IHC_SECRET_KEY")
EXAM_CODE=os.environ.get("IHC_EXAM_CODE")
if not all([ADMIN,SECRET,EXAM_CODE]) or len(SECRET)<32 or len(ADMIN)<12 or ADMIN.startswith("SUBSTITUA") or SECRET.startswith("SUBSTITUA"):
    raise RuntimeError("Configure IHC_ADMIN_PASSWORD (>=12), IHC_SECRET_KEY (>=32) e IHC_EXAM_CODE.")
DURATION=int(os.environ.get("IHC_DURATION_MINUTES","80"))*60
if not 10*60<=DURATION<=240*60: raise RuntimeError("Duração deve estar entre 10 e 240 minutos.")
app=Flask(__name__)
app.secret_key=SECRET
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax",SESSION_COOKIE_SECURE=os.environ.get("IHC_COOKIE_SECURE")=="1",PERMANENT_SESSION_LIFETIME=7200,MAX_CONTENT_LENGTH=100000)
Q=json.load(open(os.path.join(BASE,"questions.json"),encoding="utf-8"))
byid={q["id"]:q for q in Q}
def db():
    c=sqlite3.connect(DB,timeout=15);c.row_factory=sqlite3.Row;c.execute("PRAGMA journal_mode=WAL");return c
def init():
    with db() as c:
        c.executescript("""CREATE TABLE IF NOT EXISTS students(
        id INTEGER PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
        started_at INTEGER, submitted_at INTEGER, score INTEGER, ip_hash TEXT);
        CREATE TABLE IF NOT EXISTS responses(student_id INTEGER NOT NULL, question_id INTEGER NOT NULL,
        choice INTEGER NOT NULL, PRIMARY KEY(student_id,question_id));""")
init()
def csrf():
    if "csrf" not in session:session["csrf"]=secrets.token_urlsafe(24)
    return session["csrf"]
app.jinja_env.globals["csrf"]=csrf
@app.before_request
def protect():
    if request.method=="POST":
        if not secrets.compare_digest(request.form.get("csrf",""),csrf()):abort(400)
def admin_only(fn):
    @wraps(fn)
    def f(*a,**kw):
        if not session.get("admin"):return redirect(url_for("admin_login"))
        return fn(*a,**kw)
    return f
def student_only(fn):
    @wraps(fn)
    def f(*a,**kw):
        if not session.get("sid"):return redirect(url_for("index"))
        return fn(*a,**kw)
    return f
CSS="""body{font-family:system-ui,sans-serif;background:#f3f7fb;color:#152a43;margin:0}
header{background:#173957;color:white;padding:18px 6%}main{max-width:1020px;margin:28px auto;padding:0 18px}
.card{background:white;padding:22px;border-radius:13px;margin:14px 0;box-shadow:0 2px 14px #152a4312}
label{display:block;margin:12px 0}input{padding:11px;border:1px solid #9baaba;border-radius:7px;max-width:100%}
button,.btn{display:inline-block;background:#175a9c;color:white;border:0;padding:11px 18px;border-radius:8px;cursor:pointer;text-decoration:none}
button:focus-visible,a:focus-visible,input:focus-visible{outline:3px solid #ec9a25;outline-offset:3px}
small,.muted{color:#52677a}table{width:100%;border-collapse:collapse}th,td{padding:9px;border-bottom:1px solid #dce4ee;text-align:left}
.option{padding:10px;border:1px solid #e1e7ee;border-radius:8px;margin:8px 0} .option input{margin-right:10px}
.notice{background:#fff4d8;padding:12px;border-radius:8px} .row{display:flex;gap:12px;flex-wrap:wrap}
.stat{flex:1;min-width:150px;background:#e8f0f8;padding:15px;border-radius:8px}"""
BASEHTML="""<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}} — IHC</title><style>"""+CSS+"""</style></head><body><header><strong>Avaliação IHC • Técnico em Desenvolvimento de Sistemas</strong></header><main>
{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="notice">{{m}}</div>{% endfor %}{% endwith %}
"""+"""{{body|safe}}</main></body></html>"""
def page(title,body,**kw):
    from markupsafe import Markup
    return render_template_string(BASEHTML,title=title,body=Markup(render_template_string(body,**kw)))
@app.route("/",methods=["GET","POST"])
def index():
    if request.method=="POST":
        token=request.form.get("token","").strip().upper()
        code=request.form.get("code","")
        h=hashlib.sha256(token.encode()).hexdigest()
        with db() as c:
            row=c.execute("SELECT * FROM students WHERE token_hash=?",(h,)).fetchone()
        if not row or not secrets.compare_digest(code,EXAM_CODE):
            time.sleep(.35);flash("Credenciais inválidas.");return redirect(url_for("index"))
        session.clear();session["sid"]=row["id"];csrf()
        return redirect(url_for("exam"))
    return page("Acesso do aluno","""<div class="card"><h1>Entrar na avaliação</h1>
    <p>Informe seu código individual e o código da turma fornecidos pelo instrutor.</p>
    <form method="post"><input type="hidden" name="csrf" value="{{csrf()}}">
    <label>Código individual<br><input name="token" required autocomplete="off"></label>
    <label>Código da turma<br><input name="code" type="password" required></label><button>Entrar</button></form>
    <p class="muted">Uma tentativa por código. O cronômetro começa quando a avaliação é aberta.</p></div>
    <p><a href="/admin/login">Área do instrutor</a></p>""")
@app.route("/save",methods=["POST"])
@student_only
def save():
    sid=session["sid"];now=int(time.time())
    qid=request.form.get("qid","");choice=request.form.get("choice","")
    if not qid.isdigit() or not choice.isdigit():abort(400)
    qid=int(qid);choice=int(choice)
    if qid not in byid or not 0<=choice<5:abort(400)
    with db() as c:
        row=c.execute("SELECT started_at,submitted_at FROM students WHERE id=?",(sid,)).fetchone()
        if not row or row["started_at"] is None or row["submitted_at"] is not None:abort(403)
        if now-row["started_at"]>DURATION:abort(403)
        c.execute("INSERT OR REPLACE INTO responses(student_id,question_id,choice) VALUES(?,?,?)",(sid,qid,choice))
    return ("",204)

@app.route("/exam",methods=["GET","POST"])
@student_only
def exam():
    sid=session["sid"];now=int(time.time())
    with db() as c:
        row=c.execute("SELECT * FROM students WHERE id=?",(sid,)).fetchone()
        if not row:session.clear();return redirect("/")
        if row["submitted_at"] is not None:return page("Concluída","<div class='card'><h2>Avaliação encerrada</h2><p>Respostas registradas. Consulte seu instrutor para os resultados.</p></div>")
        if row["started_at"] is None:
            c.execute("UPDATE students SET started_at=? WHERE id=?",(now,sid));started=now
        else:started=row["started_at"]
        remaining=max(0,DURATION-(now-started))
        if request.method=="POST" or remaining==0:
            # Corrige e encerra mesmo se prazo expirou. Não aceita respostas após o prazo.
            selections={}
            if now-started<=DURATION+5:
                for q in Q:
                    val=request.form.get("q"+str(q["id"]),"")
                    if val.isdigit() and 0<=int(val)<5:selections[q["id"]]=int(val)
            for qid,v in selections.items():
                c.execute("INSERT OR REPLACE INTO responses VALUES(?,?,?)",(sid,qid,v))
            persisted={r["question_id"]:r["choice"] for r in c.execute(
                "SELECT question_id,choice FROM responses WHERE student_id=?",(sid,)).fetchall()}
            score=sum(persisted.get(q["id"])==q["answer"] for q in Q)
            c.execute("UPDATE students SET submitted_at=?,score=? WHERE id=? AND submitted_at IS NULL",(now,score,sid))
            return redirect(url_for("exam"))
    # Deterministic per-student permutation: stable order, does not expose answer
    import random
    rng=random.Random(int(hashlib.sha256((str(sid)+SECRET).encode()).hexdigest(),16))
    order=list(Q);rng.shuffle(order)
    with db() as c:
        saved={r["question_id"]:r["choice"] for r in c.execute(
            "SELECT question_id,choice FROM responses WHERE student_id=?",(sid,)).fetchall()}
    items=[]
    for q in order:
        perm=list(range(5));rng.shuffle(perm)
        items.append({"id":q["id"],"scenario":q["scenario"],"stem":q["stem"],"options":[(idx,q["options"][idx]) for idx in perm],"saved":saved.get(q["id"])})
    return page("Prova","""<div class="card"><h1>Avaliação objetiva de IHC</h1>
    <p>20 questões • Uma alternativa por questão • Sem consulta, conforme orientação do instrutor.</p>
    <div class="notice">Tempo restante: <strong id="clock"></strong>. Envie antes do término. Se o prazo expirar, a avaliação será encerrada.</div></div>
    <p id="save-status" role="status" aria-live="polite">Respostas são salvas ao selecionar alternativas.</p>
    <form id="test" method="post"><input type="hidden" name="csrf" value="{{csrf()}}">
    {% for q in items %}<section class="card"><small>Questão {{loop.index}} de 20</small>
    <p>{{q.scenario}}</p><strong>{{q.stem}}</strong>
    {% for j,label in q.options %}<label class="option"><input type="radio" name="q{{q.id}}" value="{{j}}" {% if q.saved == j %}checked{% endif %}> {{'ABCDE'[loop.index0]}}) {{label}}</label>{% endfor %}
    </section>{% endfor %}
    <button type="submit">Finalizar e enviar respostas</button></form>
    <script>let remaining={{remaining}};const clock=document.getElementById('clock');
    function tick(){clock.textContent=Math.floor(remaining/60)+'m '+String(remaining%60).padStart(2,'0')+'s';if(remaining<=0){document.getElementById('test').submit();return;}remaining--;}
    tick();setInterval(tick,1000);
    const csrfToken=document.querySelector('input[name="csrf"]').value;
    document.querySelectorAll('input[type="radio"]').forEach(el=>el.addEventListener('change',async()=>{
      const body=new URLSearchParams({csrf:csrfToken,qid:el.name.slice(1),choice:el.value});
      try{const r=await fetch('/save',{method:'POST',body,credentials:'same-origin'});
        if(!r.ok)throw Error('Falha no salvamento');
        document.getElementById('save-status').textContent='Resposta salva.';
      }catch(e){document.getElementById('save-status').textContent='Falha ao salvar. Verifique a conexão e envie a prova antes do prazo.';}
    }));
    </script>""",items=items,remaining=remaining)
@app.route("/admin/login",methods=["GET","POST"])
def admin_login():
    if request.method=="POST":
        if secrets.compare_digest(request.form.get("password",""),ADMIN):
            session.clear();session["admin"]=True;csrf();return redirect(url_for("dashboard"))
        time.sleep(.5);flash("Senha inválida.")
    return page("Instrutor","""<div class="card"><h1>Acesso do instrutor</h1><form method="post">
    <input type="hidden" name="csrf" value="{{csrf()}}">
    <label>Senha de administração<br><input name="password" type="password" required></label><button>Entrar</button></form></div>""")
@app.route("/admin",methods=["GET"])
@admin_only
def dashboard():
    with db() as c:
        students=c.execute("SELECT id,name,started_at,submitted_at,score FROM students ORDER BY id").fetchall()
        responses=c.execute("SELECT question_id,choice FROM responses").fetchall()
    total=len(students);started=sum(s["started_at"] is not None for s in students)
    submitted=sum(s["submitted_at"] is not None for s in students)
    scores=[s["score"] for s in students if s["score"] is not None]
    accuracy={}
    for q in Q:
        vals=[x["choice"] for x in responses if x["question_id"]==q["id"]]
        accuracy[q["id"]]=(sum(x==q["answer"] for x in vals),len(vals))
    return page("Dashboard","""<h1>Dashboard do instrutor</h1>
    <div class="row"><div class="stat">Inscritos<h2>{{total}}</h2></div><div class="stat">Iniciaram<h2>{{started}}</h2></div>
    <div class="stat">Concluíram<h2>{{submitted}}</h2></div><div class="stat">Média de acertos<h2>{{"%.1f"|format(avg)}} / 20</h2></div></div>
    <div class="card"><h2>Cadastrar estudante</h2><form method="post" action="/admin/add">
    <input type="hidden" name="csrf" value="{{csrf()}}"><label>Nome ou identificação escolar<br><input name="name" maxlength="90" required></label>
    <button>Gerar código individual</button></form>
    {% if newtoken %}<div class="notice"><strong>Código recém-criado: {{newtoken}}</strong><br>Copie agora. Por segurança, o código não será mostrado novamente.</div>{% endif %}</div>
    <div class="card"><h2>Participantes</h2><div style="overflow-x:auto"><table><tr><th>Identificação</th><th>Status</th><th>Acertos</th></tr>
    {% for s in students %}<tr><td>{{s.name}}</td><td>{{"Concluiu" if s.submitted_at else ("Em andamento" if s.started_at else "Não iniciou")}}</td>
    <td>{{s.score if s.score is not none else "—"}}</td></tr>{% endfor %}</table></div></div>
    <div class="card"><h2>Desempenho por questão</h2><table><tr><th>Questão</th><th>Capacidade</th><th>Acertos / respostas</th></tr>
    {% for q in questions %}<tr><td>{{q.id}}</td><td>{{q.capacity}}</td><td>{{accuracy[q.id][0]}} / {{accuracy[q.id][1]}}</td></tr>{% endfor %}</table></div>
    <p><a class="btn" href="/admin/export">Exportar CSV</a> <a href="/admin/logout">Sair</a></p>""",
    total=total,started=started,submitted=submitted,avg=sum(scores)/len(scores) if scores else 0,
    students=students,questions=Q,accuracy=accuracy,newtoken=session.pop("newtoken",""))
@app.route("/admin/add",methods=["POST"])
@admin_only
def add():
    name=request.form.get("name","").strip()
    if not 2<=len(name)<=90:abort(400)
    token=secrets.token_hex(5).upper()
    with db() as c:c.execute("INSERT INTO students(name,token_hash) VALUES(?,?)",(name,hashlib.sha256(token.encode()).hexdigest()))
    session["newtoken"]=token
    return redirect(url_for("dashboard"))
@app.route("/admin/export")
@admin_only
def export():
    with db() as c:rows=c.execute("SELECT id,name,started_at,submitted_at,score FROM students ORDER BY id").fetchall()
    out=io.StringIO();w=csv.writer(out);w.writerow(["id","identificacao","inicio_unix","conclusao_unix","acertos_20","nota_10"])
    for s in rows:
        w.writerow([s["id"],s["name"],s["started_at"],s["submitted_at"],s["score"],round(s["score"]*.5,2) if s["score"] is not None else ""])
    return Response("\ufeff"+out.getvalue(),mimetype="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=ihc_resultados.csv"})
@app.route("/admin/logout")
def logout():
    session.clear();return redirect("/")
@app.after_request
def headers(resp):
    resp.headers["Cache-Control"]="no-store"
    resp.headers["X-Content-Type-Options"]="nosniff"
    resp.headers["X-Frame-Options"]="DENY"
    resp.headers["Referrer-Policy"]="no-referrer"
    resp.headers["Content-Security-Policy"]="default-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    return resp
if __name__=="__main__":
    app.run(host="127.0.0.1",port=5000,debug=False)
