# Implantação online — Avaliação IHC (20 questões)

## Escopo
Aplicação Flask + SQLite, executada em contêiner, com proxy HTTPS Caddy e painel administrativo.
A implantação **não foi executada ou auditada em servidor público**. Faça homologação antes de coletar dados reais.

## Pré-requisitos
- VPS Linux com IP público, Docker Engine e Docker Compose Plugin instalados.
- Domínio/subdomínio sob seu controle (ex.: `prova.suaescola.com.br`).
- Registro DNS A apontando para o IP público da VPS.
- Portas 80 e 443 liberadas no firewall; SSH restrito aos administradores.
- Aprovação do setor de TI e do responsável institucional pelo tratamento de dados.

## Instalação
1. Copie esta pasta para a VPS (sem dados reais de estudantes).
2. Copie `.env.example` para `.env` e edite com valores exclusivos.
3. Gere chave: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.
4. Defina `EXAM_DOMAIN` com o subdomínio apontado no DNS.
5. Proteja o arquivo: `chmod 600 .env`.
6. Inicie: `docker compose up -d --build`.
7. Confira: `docker compose ps` e `docker compose logs --tail=100 caddy`.
8. Abra `https://SEU_DOMINIO/admin/login` e cadastre estudantes.
9. Distribua o código individual e o código da turma por canais adequados.
10. Aplique primeiro uma prova simulada com contas de teste e dispositivos diferentes.

O Caddy solicita certificado HTTPS automaticamente quando o domínio aponta para o servidor e as portas estão acessíveis. Não compartilhe o `.env`.

## Operação e proteção
- O gabarito fica no servidor; não é enviado ao navegador do aluno.
- Questões e alternativas são embaralhadas de forma estável por aluno.
- Uma tentativa por código individual; prazo validado no servidor.
- Respostas são salvas ao selecionar cada alternativa e também ao finalizar.
- Em perda de conexão, o aluno pode reabrir a prova com o mesmo código enquanto o prazo não expirar.
- A ausência de envio final até o limite encerra a tentativa ao próximo acesso; respostas já salvas são consideradas.
- A contagem de tempo começa ao abrir a prova, não ao receber o código.
- Há CSRF, cookies Secure/HttpOnly/SameSite e separação do painel.
- **Não há limitação persistente de tentativas de login nem autenticação multifator**; configure proteção adicional no proxy/serviço de identidade antes de produção.
- **SQLite é apropriado para turmas pequenas e carga moderada**; teste concorrência antes de aplicar a grupos grandes.
- Não use essa solução como plataforma de prova de alto risco sem auditoria independente.

## Backup
O banco está no volume Docker `ihc_data`. Faça backups regulares e teste a restauração.
Para cópia consistente com aplicação ativa, utilize API de backup SQLite ou pare a aplicação antes de copiar o banco.
Exemplo com aplicação parada:
`docker compose stop app`
`docker compose run --rm --no-deps --entrypoint python app -c "import sqlite3; src=sqlite3.connect('/data/ihc.db'); dst=sqlite3.connect('/data/backup.db'); src.backup(dst); dst.close(); src.close()"`
`docker compose start app`
**Atenção:** o backup no exemplo permanece no mesmo volume; copie-o para local externo protegido.

## Limitações e LGPD
- Evite armazenar CPF, documentos ou dados sensíveis. Use matrícula ou identificador escolar mínimo.
- Defina base legal, finalidade, transparência, retenção, descarte e responsáveis pelo tratamento.
- Acesso ao dashboard e exportações CSV deve ser restrito.
- O sistema não oferece monitoramento de tela, bloqueio de outros aplicativos nem detecção confiável de cola.
- A aplicação não substitui uma plataforma institucional homologada.
- A avaliação é autoral e inspirada em situações profissionais; não é exame oficial SAEP.

## Problemas comuns
- HTTPS indisponível: confira DNS, portas 80/443, logs do Caddy.
- Falha no login: confira variáveis `.env`, sem expor segredos em prints.
- Erro de permissão: o contêiner roda com usuário não privilegiado (UID 10001); volume precisa permitir escrita.
- Não altere `IHC_SECRET_KEY` durante a prova: isso invalida sessões existentes.
- Nunca use `python app.py` diretamente exposto na internet.
