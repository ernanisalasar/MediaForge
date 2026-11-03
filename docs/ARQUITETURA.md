# Arquitetura

> MediaForge — Desenvolvido por Ernani Salasar. Copyright (c) 2026 Ernani Salasar.

```
 ui/main_window ──► TaskManager ──► Job (download | conversão)
        │                 │               │
        │  Signal (thread-safe)           ├─ DownloadService ─► SourcePolicy + sessão "segura" / yt-dlp
        ◄─────────────────┘               └─ MediaService ──► FFprobe/FFmpeg (subprocess, lista de args)
        └─► HistoryStore (SQLite)  ·  Settings (JSON)
```

- **Interface responsiva:** a UI nunca bloqueia. Validação de link e leitura de metadados rodam em `QThreadPool`;
  downloads e conversões rodam no `TaskManager` (`ThreadPoolExecutor`, 2 trabalhadores). As atualizações voltam à thread da
  UI por um `Signal` (conexão enfileirada automaticamente pelo Qt).
- **TaskManager** não depende de Qt: recebe callbacks `on_update`/`on_finished`, limita notificações a ~10/s, trata
  cancelamento (inclusive tarefas ainda na fila) e converte exceções em estados `Falhou`/`Cancelado`.
- **Encadeamento:** tarefas podem ter um `followup` (ex.: converter após baixar), executado na thread da UI quando a tarefa conclui.
- **MediaService:** valida opções contra os metadados da origem (sem aumentar resolução, bitrate válido para o codec),
  grava em arquivo temporário `.nome.xxxx.part.ext`, lê `-progress pipe:1`, e só renomeia após verificar com o FFprobe.
- **Cancelamento do FFmpeg:** uma thread vigia o evento, chama `terminate()` e, se necessário, `kill()` após 5 s.
- **Formatos reais:** `available_encoders()` consulta `ffmpeg -encoders`; formatos sem codificador ficam desativados.
- **YouTube:** yt-dlp consulta metadados e baixa um único vídeo público na melhor combinação de vídeo e áudio disponível.
  Com a opção **Original** e sem conversão, a fonte pode preservar 1080p, 1440p ou 2160p (4K), quando os disponibilizar.
  No modo Áudio, o fluxo selecionado é `bestaudio` e o FFmpeg realiza a saída no formato escolhido. As requisições usam a
  política de DNS, redirecionamento e conexão TCP, sem cookies de navegador ou proxy. Conversão e miniatura são locais.
- **Dados:** `%LOCALAPPDATA%\MediaForgeLocal\{history.db,settings.json}`.
