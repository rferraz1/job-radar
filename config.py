
import os
from dotenv import load_dotenv

load_dotenv()

# Adaptado do perfil original (Dados/BI) pro perfil do Rodolfo: dev
# júnior/estágio/trainee, sem exigência de senioridade alta. Cargo forte:
# título que já declara júnior/estágio/trainee no próprio nome, sem
# possibilidade real de ser vaga sênior/pleno.
KEYWORDS_CARGO_FORTE = [
    "Desenvolvedor Júnior",
    "Desenvolvedora Júnior",
    "Programador Júnior",
    "Programadora Júnior",
    "Junior Developer",
    "Junior Software Engineer",
    "Software Engineer Intern",
    "Software Developer Intern",
    "Estagiário de TI",
    "Estagiária de TI",
    "Estágio em Tecnologia",
    "Estágio em Tecnologia da Informação",
    "Estágio em Desenvolvimento",
    "Estágio de Desenvolvimento",
    "Estágio em Programação",
    "Trainee de Tecnologia",
    "Trainee de Desenvolvimento",
    "Trainee Developer",
    "Analista de Suporte Júnior",
    "Técnico de Suporte Júnior",
    "Suporte Técnico Júnior",
    "Assistente de TI",
]

# Cargo ambíguo: título que também é usado em vaga de qualquer senioridade
# (ex: "Desenvolvedor" sozinho existe de júnior a sênior). Só conta como
# match se o título TAMBÉM tiver um QUALIFICADORES_JUNIOR junto — é o que
# permite ir adicionando cargo adjacente (Analista de Sistemas, Suporte
# Técnico) sem cada um virar fonte de ruído sozinho.
KEYWORDS_CARGO_AMBIGUO = [
    "Desenvolvedor",
    "Desenvolvedora",
    "Programador",
    "Programadora",
    "Developer",
    "Software Engineer",
    "Analista de Sistemas",
    "Analista de TI",
    "Suporte Técnico",
    "Analista de Suporte",
    "Estagiário",
    "Estagiária",
    "Trainee",
]

# Termo que precisa aparecer junto no título quando o cargo é ambíguo, pra
# confirmar que é vaga júnior/estágio/trainee e não pleno/sênior.
QUALIFICADORES_DADOS = [
    "júnior",
    "junior",
    "jr",
    "trainee",
    "estágio",
    "estagiário",
    "estagiária",
    "iniciante",
    "entry level",
    "primeiro emprego",
]

# Ferramenta/stack que aparece como núcleo do título ("Desenvolvedor React
# Júnior"). Só conta como match se o título TAMBÉM tiver uma palavra de
# cargo — evita que "Python" sozinho aprove qualquer vaga que só cite a
# linguagem como diferencial.
FERRAMENTAS_TITULO = [
    "Python",
    "JavaScript",
    "React",
    "Node",
    "Node.js",
    "TypeScript",
]

# Palavra de cargo que confirma que a vaga de ferramenta é de
# desenvolvimento/suporte júnior.
QUALIFICADORES_CARGO = [
    "desenvolvedor",
    "desenvolvedora",
    "programador",
    "programadora",
    "developer",
    "estagiário",
    "estagiária",
    "trainee",
    "suporte",
]

KEYWORDS = KEYWORDS_CARGO_FORTE + KEYWORDS_CARGO_AMBIGUO

# Termos de busca enviados a cada site. Ficam separados das KEYWORDS de
# propósito: TERMOS_BUSCA é a rede ampla (o que é pesquisado em cada site,
# incluindo termos de ferramenta/stack pra achar vaga com título atípico),
# enquanto KEYWORDS é o filtro final e só olha o título da vaga já
# encontrada. Um termo de ferramenta (ex: "dax") só resulta em notificação
# se o TÍTULO da vaga também bater com uma keyword de cargo — isso evita
# falso positivo de vaga que só cita a ferramenta como diferencial.
#
# TERMOS_CARGO é derivado direto de KEYWORDS (em vez de mantido à mão em
# lista separada) — antes as duas listas divergiam: metade das KEYWORDS
# (ex: "Desenvolvedor BI", "BI Analyst", "Analista de Negócios") nunca era
# buscada de verdade, só existia como filtro, então só pegava essas vagas
# por sorte via outro termo. Com a derivação automática isso não pode mais
# acontecer — toda keyword nova em KEYWORDS já vira busca também.
TERMOS_CARGO_EXTRA = [
    # termos mais amplos que a keyword exata, mantidos por dar rede mais
    # larga na busca (a keyword em si é mais restrita, de propósito, pra
    # não gerar falso positivo no filtro de título).
    "desenvolvedor junior",
    "programador junior",
]

TERMOS_CARGO = sorted(set(k.lower() for k in KEYWORDS) | set(TERMOS_CARGO_EXTRA))

# MEDIDO em jobradar.log (12 rodízios completos, Gupy+99Jobs+GeekHunter+
# Solides): "dax" e "power query" nunca resultaram em nenhuma vaga nova
# notificada nessas 4 fontes — 0 em 48 buscas cada, a maioria vazia
# ("0 resultados reais") e o resto timeout. "microsoft fabric" teve 1 vaga
# no log inteiro (363 notificações) com o termo no título, e essa vaga
# também tinha "Power BI"/"Analista de BI" no título — já seria achada por
# termo que continua na lista. Timeout: os 3 termos concentraram metade
# (13 de 26) dos timeouts dessas 4 fontes sendo só 3 dos 42 termos (7%) —
# confirma o padrão relatado. Removidos por render zero e custarem sessão
# igual a um termo de cargo.
TERMOS_FERRAMENTA = [
    "python",
    "javascript",
    "react",
    "node",
    "typescript",
    "sql",
]

TERMOS_BUSCA = TERMOS_CARGO + TERMOS_FERRAMENTA

# Medido: os TERMOS_BUSCA inteiros (hoje 42) rodando em TODO ciclo é o que
# gera as centenas de sessões de navegador por execução — o custo cresce
# linear com o tamanho da lista, e a lista só cresce (mais ainda com a
# expansão internacional puxando mais termos no radar). TERMOS_POR_CICLO é
# o tamanho do BLOCO usado por ciclo, não o total de termos — main.py roda
# um bloco por vez em rodízio (ver _proximo_bloco_termos) e avança pro
# próximo bloco no ciclo seguinte, salvando a posição no jobs.db. Isso
# desacopla custo por ciclo de tamanho da lista: dobrar TERMOS_BUSCA dobra
# quantos ciclos até cobrir tudo de novo, não o custo de cada ciclo.
TERMOS_POR_CICLO = 10

CIDADES = [
    # Só "Remoto" de propósito: Rodolfo quer 100% home office (regra
    # explícita, não critério a reconsiderar) — cidade presencial/híbrida
    # fica fora, diferente do perfil original (que aceitava presencial na
    # região do autor).
    "Remoto",
]

# MEDIDO: "Data Analyst @ Lisboa" e "Analista de Datos @ Madrid" reprovavam
# na localização, não no cargo — CIDADES acima é whitelist só de cidade
# brasileira, e a expansão de LOCATIONS_LINKEDIN pra Argentina/Chile (ver
# abaixo) passou a trazer vaga presencial/híbrida em Portugal/Espanha de
# vez em quando junto. Lista SEPARADA (não misturada em CIDADES, que
# continua só-Brasil de propósito — ver decisão registrada na criação do
# config_intl.py) com toggle próprio, pra dar pra ligar/desligar esse eixo
# sem mexer no resto do filtro. Canônica aqui porque config_intl.py já
# importa de config.py (não o contrário) — o pipeline internacional reusa
# essa mesma lista em vez de manter uma cópia (risco de divergir, mesmo
# motivo da unificação de _contem_termo/_tem_termo).
CIDADES_EUROPA_IBERICA = [
    "Portugal",
    "Lisboa",
    "Porto",
    "Braga",
    "Espanha",
    "España",
    "Spain",
    "Madrid",
    "Barcelona",
    "Valencia",
]

# Toggle independente do ATIVAR_EIXO_IBERICO de config_intl.py — são dois
# eixos diferentes (esse aqui é do pipeline BR/main.py, aquele é do
# pipeline internacional/main_intl.py), cada um com seu próprio liga/
# desliga, mesmo compartilhando a mesma lista de cidades acima.
#
# DESLIGADO: do mercado internacional, só interessa vaga remota — vaga
# presencial/híbrida em Lisboa/Madrid (o que esse eixo notifica, marcada
# "exploratória") não é o que o usuário quer. CIDADES_EUROPA_IBERICA
# continua definida (não precisa apagar) pra caso o eixo volte a ser
# ligado depois — só o toggle muda.
ATIVAR_EIXO_IBERICO_BR = False

# LinkedInScraper é a única fonte do pipeline BR que também alcança vaga
# fora do Brasil (as outras são portais brasileiros) — mas até aqui rodava
# só com location=Brasil fixo no código (scrapers/linkedin.py:88), então
# essa "porta pra fora" nunca era usada.
#
# Mercado "casa": busca modalidade completa (presencial/híbrida + remoto),
# porque o usuário mora aqui e vaga local de verdade interessa.
LOCATIONS_LINKEDIN = ["Brasil"]

# Mercados adicionais: só busca REMOTA (f_WT=2) — vaga presencial/híbrida
# num país onde o usuário não mora não serve, então nem faz sentido gastar
# a passada nacional ali (era puro desperdício: Argentina/Chile já rodavam
# as duas passadas antes, mas a nacional nunca batia em CIDADES mesmo,
# que é só cidade brasileira). Espanhol ou português — mesmo critério do
# pipeline internacional. Lista reaproveita exatamente os países já usados
# e testados ao vivo no endpoint do LinkedIn em config_intl.py
# (LOCATIONS_INTL) — evita arriscar nome de país nunca testado (grafia
# errada ou região que o LinkedIn não resolve como location de verdade,
# como já visto com "LATAM"/"Latin America").
LOCATIONS_LINKEDIN_REMOTO_APENAS = []  # Rodolfo não quer mercado fora do Brasil por ora — corta a passada extra

# Mercado que a vaga remota precisa aceitar pra contar, quando o texto de
# local DECLARA um escopo geográfico ("Remote — US only", "Remote — India").
# Ver Job.escopo_remoto/RegrasFiltro.mercados_remoto_aceitos em job.py — sem
# isso, uma vaga remota só pra outro país passava igual a uma remota de
# verdade pro Brasil. Vaga remota SEM escopo declarado no texto (a grande
# maioria) continua batendo normalmente, isso só filtra quando a fonte
# EXPLICITA um mercado incompatível.
#
# MEDIDO: Argentina/Chile/México/Colômbia ENTRAM nominalmente agora — a
# suposição de que "LATAM" cobria os quatro como guarda-chuva só valia
# enquanto extrair_escopo_remoto resolvia o texto pra "LATAM" literal.
# Depois que passou a reconhecer cidade (Buenos Aires/Santiago/Cidade do
# México/Bogotá — ver _CIDADES_MERCADO em job.py), o escopo passou a
# resolver pro PAÍS específico, não mais pro guarda-chuva — e o país
# específico nunca esteve nessa lista. Resultado: LOCATIONS_LINKEDIN_
# REMOTO_APENAS pagava o custo de buscar nesses 4 países e o filtro
# descartava tudo que a busca trazia de lá. "LATAM" continua na lista pra
# quando o texto disser isso literalmente (guarda-chuva de verdade, não
# substituto de nome de país). Portugal e Espanha entraram nominalmente
# pelo mesmo motivo, desde antes.
MERCADOS_REMOTO_ACEITOS = ["Brasil"]

INTERVALO_MINUTOS = int(os.getenv("INTERVALO_MINUTOS", 180))

# Digest ranqueado (item 08): vaga com Job.pontuar_relevancia() >= este
# limiar notifica na hora (como sempre foi); abaixo disso, fica na fila do
# digest diário — ver _enviar_digest_diario em main.py.
#
# MEDIDO: rodei o score contra as ~305 vagas do jobs.db real que ainda
# batem as regras atuais. Distribuição: score 4 (2%), 5 (24%), 6 (67%),
# 7 (5%), 8 (2%) — nada em 9-10 na amostra (exige acertar praticamente
# todo sinal ao mesmo tempo: cargo forte + ferramenta + senioridade alvo +
# mercado confirmado). Limiar 7 deixa ~7% imediata e ~93% no digest — bate
# com o pedido ("vaga de score alto na hora, resto agrupado"); 6 deixava
# 74% imediata (pouca redução de ruído); 8 deixava só 2% (digest com
# praticamente tudo, quase nenhuma vaga "excelente" se destacando na hora).
LIMIAR_DIGEST_IMEDIATO = 7

# Hora UTC em que o digest diário dispara (uma vez por perfil, por dia —
# ver _enviar_digest_diario). 0 = meia-noite UTC = 21h em Brasília (UTC-3).
# O cron do workflow (0 */3 * * *) já passa por essa hora exata todo dia,
# então não precisa de agendamento à parte.
DIGEST_HORA_UTC = 0

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "jobs.db")