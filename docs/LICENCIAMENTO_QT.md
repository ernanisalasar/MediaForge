# Licenciamento do Qt na distribuição Windows

## Componentes identificados

A distribuição onedir examinada foi construída com:

- Qt 6.12.0 (`PySide6-Essentials` 6.12.0);
- PySide6 6.12.0;
- Shiboken6 6.12.0.

Os metadados instalados de `PySide6-Essentials` e `shiboken6` declaram `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. Isso descreve alternativas de licenciamento declaradas pelo pacote; não determina, por si só, a licença de cada arquivo Qt nem comprova que uma distribuição específica cumpre qualquer dessas licenças. Os textos fornecidos nos arquivos-fonte oficiais estão em `LICENSES/Qt/`. Qt também contém componentes com avisos e licenças próprios, por isso os textos de licença por módulo foram preservados.

## Bibliotecas e plugins distribuídos

Os arquivos observados no pacote PyInstaller estão em `MediaForgeLocal/_internal/`:

- `PySide6/Qt6Core.dll`, `Qt6Gui.dll`, `Qt6Network.dll`, `Qt6Svg.dll` e `Qt6Widgets.dll`;
- bindings `PySide6/QtCore.pyd`, `QtGui.pyd`, `QtNetwork.pyd`, `QtWidgets.pyd` e `pyside6.abi3.dll`;
- Shiboken em `shiboken6/Shiboken.pyd` e `shiboken6/shiboken6.abi3.dll`;
- plugins em `PySide6/plugins/`: `generic/qtuiotouchplugin.dll`, `iconengines/qsvgicon.dll`, plugins `imageformats` (`qgif`, `qicns`, `qico`, `qjpeg`, `qsvg`, `qtga`, `qtiff`, `qwbmp`, `qwebp`), `networkinformation/qnetworklistmanager.dll`, `platforms` (`qdirect2d`, `qminimal`, `qoffscreen`, `qwindows`), `styles/qmodernwindowsstyle.dll` e plugins `tls` (`qcertonlybackend`, `qopensslbackend`, `qschannelbackend`).

Essa lista é do pacote examinado, não uma afirmação de que os plugins tenham todos a mesma licença. Os avisos dos módulos-fonte Qt e dos componentes de terceiros estão organizados em `LICENSES/Qt/`; a composição e os arquivos do executável devem ser rechecados em cada versão distribuída.

## Fontes correspondentes

Os quatro arquivos-fonte Qt 6.12.0 já obtidos de `download.qt.io` foram mantidos fora do repositório, para evitar adicionar arquivos ZIP grandes ao código-fonte. Seus URLs oficiais, tamanhos e SHA-256 estão em [Manifesto das fontes Qt 6.12.0](./qt-source-manifest.md).

O pacote separado `MediaForgeLocal-Qt-Corresponding-Source-6.12.0.zip` reúne esses quatro arquivos ZIP oficiais e o manifesto. Ele deve ser fornecido junto com a distribuição binária que use essas bibliotecas. O ZIP de fontes contém os projetos QtBase, QtSvg, QtImageFormats e PySide/Shiboken da mesma versão; o manifesto permite verificar que os arquivos do pacote correspondem aos arquivos baixados. Isso não prova que cada binário do wheel foi construído sem patches ou com as mesmas opções: os dados de proveniência da compilação binária ainda precisam ser obtidos e preservados.

Para verificar os arquivos-fonte, calcule SHA-256 e compare com o manifesto antes de extrair. Mantenha os arquivos e a documentação com o pacote binário correspondente; não dependa de links externos como único meio de acesso às fontes.

## Substituição de bibliotecas Qt

O formato onedir mantém as DLLs Qt e os plugins como arquivos separados do executável principal, sob `MediaForgeLocal/_internal/PySide6/`. Isso permite testar substituições sem reconstruir o executável principal, desde que as bibliotecas substitutas sejam binariamente compatíveis. O executável contém bindings Python compilados (`.pyd`) e Shiboken; a simples troca de DLLs não substitui esses bindings.

Procedimento conservador para uma pessoa que reconstruiu uma biblioteca Qt modificada:

1. Preserve uma cópia íntegra e não execute o aplicativo durante a troca.
2. Obtenha o código-fonte correspondente e as instruções de build do componente, mantendo a versão, arquitetura, ABI, toolchain e opções compatíveis com o pacote. Os ZIPs deste pacote fornecem as fontes upstream Qt 6.12.0, não uma receita de build binário completa.
3. Faça a substituição apenas dos arquivos compartilhados que foram reconstruídos e dos plugins correspondentes, preservando a estrutura de diretórios em `_internal/PySide6/`. Não substitua `.pyd`, Shiboken ou plugins não relacionados por arquivos de ABI/arquitetura desconhecida.
4. Inicie o aplicativo a partir da cópia de teste e exercite a interface e os recursos Qt usados. Verifique carregamento de plugins e registre os arquivos, hashes, configuração da compilação e resultado. Se houver erro, restaure a cópia original.

**Limite de validação:** a disposição dos arquivos confirma que as DLLs e plugins podem ser substituídos como arquivos, mas ainda não foi realizado um teste com uma biblioteca Qt modificada e reconstruída. Portanto, a substituição em runtime não está validada para esta distribuição.

## Obrigações e pendências LGPL

Se a distribuição usar componentes sob LGPL, obrigações potencialmente aplicáveis incluem disponibilizar os avisos e textos de licença exigidos, fornecer o código-fonte correspondente nos termos aplicáveis e não impedir a substituição/depuração das bibliotecas licenciadas. A aplicação usa uma distribuição onedir com bibliotecas dinâmicas separadas, mas isso, isoladamente, não comprova o cumprimento das condições da LGPL.

Antes de uma distribuição pública, ainda é necessário:

- determinar e registrar a licença aplicável a cada DLL, binding e plugin efetivamente distribuído, incluindo as alternativas declaradas pelos metadados e eventuais componentes de terceiros;
- confirmar que os fontes e a informação de build correspondem aos binários exatos, inclusive eventuais patches, configurações e toolchain; os arquivos presentes fornecem fontes upstream da versão, mas não evidência desses detalhes;
- revisar a forma de distribuição, os avisos fornecidos, o acesso ao código-fonte e as condições de substituição/reverse engineering aplicáveis;
- testar uma substituição real por build Qt modificada compatível e registrar o procedimento;
- revisar separadamente os termos de componentes não Qt empacotados, inclusive os runtimes Microsoft observados.

Não há neste repositório parecer jurídico nem declaração de conformidade LGPL. O pacote de fontes e os textos de licença são materiais de apoio e não eliminam essas pendências técnicas e jurídicas.
