# Portal de Avaliação IHC — 20 questões

Sistema Flask + SQLite para aplicação da avaliação de IHC com acesso por código individual e dashboard.

## Instalação

Requer Python 3.10+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Configure as variáveis de ambiente antes de iniciar (não use literalmente os valores do arquivo `.env.example`):

**Linux/macOS**
```bash
export IHC_ADMIN_PASSWORD='SENHA_FORTE_EXCLUSIVA_COM_20_OU_MAIS_CARACTERES'
export IHC_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
export IHC_EXAM_CODE='CODIGO_PRIVADO_DA_TURMA'
python app.py
```

**Windows PowerShell**
```powershell
$env:IHC_ADMIN_PASSWORD='SENHA_FORTE_EXCLUSIVA_COM_20_OU_MAIS_CARACTERES'
$env:IHC_SECRET_KEY=python -c "import secrets;print(secrets.token_urlsafe(48))"
$env:IHC_EXAM_CODE='CODIGO_PRIVADO_DA_TURMA'
python app.py
```

Abra http://127.0.0.1:5000/admin/login no computador que executa o programa.

## Fluxo do instrutor
1. Entre no painel administrativo.
2. Cadastre cada estudante e anote o código individual exibido **uma única vez**.
3. Distribua código individual e código da turma separadamente.
4. Acompanhe status, acertos e desempenho por questão.
5. Exporte resultados em CSV.

## Acesso dos estudantes em rede
O modo padrão `python app.py` atende **somente o próprio computador**, para reduzir exposição acidental.
Para usar em laboratório/rede, configure HTTPS por um proxy reverso e rode com um servidor WSGI,
por exemplo `waitress-serve --listen=127.0.0.1:8080 app:app`, publicando exclusivamente o
endereço HTTPS do proxy. Não exponha Flask diretamente na internet. Ajuste
`IHC_COOKIE_SECURE=1` quando HTTPS estiver configurado.

## Segurança e limitações
- Códigos individuais aleatórios são armazenados somente como hash SHA-256.
- Respostas corretas e correção ficam no servidor.
- Ordem de questões e alternativas é embaralhada por estudante.
- Uma tentativa por código, prazo controlado no servidor e finalização irreversível.
- Formulários usam token CSRF, cookies HttpOnly/SameSite e cabeçalhos de proteção.
- O painel é restrito ao instrutor e exporta CSV.
- **Não há garantia contra cola, captura de tela, compartilhamento de códigos ou dispositivos externos.**
- É um protótipo funcional para implantação supervisionada, **não um sistema homologado para uso institucional**.
- Para produção, adicione HTTPS, autenticação institucional, limitação de tentativas persistente,
  backups, política de retenção de dados, logs de auditoria e revisão de segurança/LGPD.
- Não armazene dados sensíveis desnecessários; utilize identificação escolar mínima e acesso restrito.
- A avaliação é autoral, inspirada no estilo de situações profissionais, não oficial SAEP.

## Dados e recuperação
O banco `ihc.db` é criado na primeira execução. Faça backup seguro com o sistema parado.
Para nova turma, use um banco separado via `IHC_DB_PATH`.
