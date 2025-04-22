# Wolf-v8.5 - Downloader de Mídia

## 📌 Visão Geral
Wolf-v8.5 é um script Bash para baixar músicas e vídeos de várias plataformas como YouTube e Spotify, convertendo-os para MP3 quando necessário.

## 🌟 Recursos
- Download de vídeos do YouTube (via yt-dlp)
- Download/conversão de músicas do Spotify (via spotdl)
- Conversão para MP3 automática
- Suporte ao Termux (Android)
- Interface simples com banners coloridos

## 📥 Plataformas Suportadas
- YouTube
- Spotify
- Vários outros sites suportados pelo yt-dlp

## 🛠️ Pré-requisitos
- Python 3
- pip/pip3
- ffmpeg (instalado automaticamente no Termux)

## ⚙️ Instalação
1. Clone o repositório:
```bash
git clone https://github.com/jottap-termux/Wolf-v8.5.git
cd Wolf-v8.5
```

2. Execute o script de instalação:
```bash
chmod +x install.sh
./install.sh
```

3. (Opcional) Para instalar manualmente as dependências:
```bash
pip install --upgrade requests yt-dlp spotdl
```

## 🚀 Como Usar
Execute o script principal:
```bash
./wolf-v8.sh
```

Siga as instruções no menu para:
1. Baixar músicas/vídeos
2. Definir qualidade
3. Escolher formato de saída

## 🛠️ Dependências
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Fork do youtube-dl com melhorias
- [spotdl](https://github.com/spotDL/spotify-downloader) - Downloader de músicas do Spotify
- [ffmpeg](https://ffmpeg.org/) - Para conversão de formatos

## ❓ Problemas Comuns/Soluções
- **Erro de permissão**: Execute com `sudo` ou use `--user`
- **Faltando ffmpeg**: No Termux, execute `pkg install ffmpeg`
- **Erros no spotdl**: Atualize com `pip install --upgrade spotdl`

## 📄 Licença
Este projeto está sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 👥 Créditos
- Desenvolvido por [jottap-termux](https://github.com/jottap-termux)
- Baseado em yt-dlp e spotdl

## 🔗 Links Úteis
- [Lista de sites suportados pelo yt-dlp](https://yt-dlp.org/supportedsites.html)
- [Documentação do spotdl](https://spotdl.readthedocs.io/)
