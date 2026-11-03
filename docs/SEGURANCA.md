# Segurança e privacidade

> MediaForge — Desenvolvido por Ernani Salasar. Copyright (c) 2026 Ernani Salasar.

## Rede / SSRF
1. `SourcePolicy.validate_url` aceita só `http`/`https`, rejeita credenciais na URL, hosts internos (`localhost`, `*.internal`,
   `*.local`…), e resolve o DNS exigindo que **todos** os IPs sejam públicos (bloqueia loopback, privados, link-local,
   CGNAT, multicast, reservados e endereços de metadados de nuvem, inclusive IPv4 mapeado em IPv6 e formas numéricas como `2130706433`).
2. Nos links diretos, redirecionamentos são seguidos **manualmente** (máx. 5); cada destino é revalidado antes da requisição.
   No yt-dlp, o adaptador seguro valida cada requisição/redirecionamento. Downgrade HTTPS→HTTP é bloqueado nos links diretos.
3. Na conexão TCP (`_connect_checked`) o IP realmente usado é validado de novo e a conexão é feita nesse IP — cobre DNS rebinding.
4. A sessão ignora proxies/variáveis de ambiente (`trust_env=False`), rejeita cookies recebidos e remove cabeçalhos de cookie/autenticação.

## Conteúdo baixado
Verifica o `Content-Type`, rejeita HTML (inclusive disfarçado com extensão de vídeo, olhando os primeiros 512 bytes) e playlists
HLS/DASH,
respeita limite de tamanho (cabeçalho e fluxo), baixa em blocos para `.part` e renomeia ao final; não substitui arquivos sem confirmação.
Em cancelamento ou conteúdo rejeitado o temporário é removido; em falha de rede ele é **mantido** para diagnóstico e o caminho é informado.

## Execução de processos
`subprocess` sempre com lista de argumentos, sem `shell=True`; caminhos absolutos (nomes iniciados por `-` não viram opções).

## Arquivos
`sanitize_filename` remove diretórios, caracteres ilegais, caracteres de controle/RTL, nomes reservados do Windows e limita o tamanho;
a saída nunca coincide com o arquivo de origem e fica restrita à pasta escolhida.

## Privacidade
Sem telemetria, analytics, anúncios ou envio de arquivos. O histórico guarda nome, data, operação, formato, estado, tamanho e
**apenas o host** da origem — nunca URL completa, query, cookies ou tokens. Retenção configurável (90 dias por padrão).

## YouTube
O yt-dlp é usado somente para URLs de vídeos individuais do YouTube; playlists e transmissões ao vivo são rejeitadas. O fluxo
substitui os handlers de rede padrão do yt-dlp por um único handler baseado na sessão segura do app: cada URL é validada antes
da requisição, todos os IPs resolvidos precisam ser públicos e o IP efetivamente conectado é verificado novamente. A sessão
não usa proxies, cookies de navegador, credenciais ou cabeçalhos de autenticação; handlers alternativos sem essas garantias
ficam desativados. A rede é usada para buscar metadados e o conteúdo público solicitado, nunca para enviar arquivos locais.
Vídeos privados, restritos por idade/região, transmissões ao vivo e formatos incompatíveis podem falhar. Os testes mockam o
yt-dlp e não acessam a internet real.
