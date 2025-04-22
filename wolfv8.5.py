#!/usr/bin/env python3
import os
import sys
import subprocess
import requests
import shutil
import time
import re
import signal
from threading import Thread
from queue import Queue, Empty
from time import sleep

# Configurações
HOME = os.path.expanduser("~")
PASTA_DOWNLOADS = "/sdcard/WolfVideos"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
ARQUIVO_COOKIES = "/sdcard/cookies.txt"
URL_ATUALIZACAO_COOKIES = "https://jottap-termux.github.io/cookies.txt"
ATUALIZAR_COOKIES_AUTO = True
TERMUX_PATH = "/data/data/com.termux/files/home/.local/bin"
ARQUIVO_DOWNLOADS_PARCIAL = os.path.join(PASTA_DOWNLOADS, ".downloads_parciais.txt")
                                                                                        # Formatos pré-definidos
FORMATOS_VIDEO = {
    '1': {'desc': '🎯 Best quality (4K if available)', 'code': 'best'},
    '2': {'desc': '🖥 1080p HD', 'code': '137+140'},
    '3': {'desc': '💻 720p HD', 'code': '22'},
    '4': {'desc': '📱 480p', 'code': '135+140'},
    '5': {'desc': '📼 360p', 'code': '18'}
}

FORMATOS_AUDIO = {
    '1': {'desc': '🎧 MP3 (High quality 320kbps)', 'code': 'mp3', 'params': '-x --audio-format mp3 --audio-quality 0'},
    '2': {'desc': '🎵 AAC (High quality)', 'code': 'aac', 'params': '-x --audio-format aac'},
    '3': {'desc': '🎼 FLAC (Lossless)', 'code': 'flac', 'params': '-x --audio-format flac'},
    '4': {'desc': '🎤 M4A (YouTube default)', 'code': 'm4a', 'params': '-x --audio-format m4a'},
    '5': {'desc': '🎶 OPUS (Efficient)', 'code': 'opus', 'params': '-x --audio-format opus'},
    '6': {'desc': '💿 MP3 with cover art', 'code': 'mp3', 'params': '-x --audio-format mp3 --audio-quality 0 --embed-thumbnail --add-metadata'}
}

# Variável global para controle de interrupção
download_interrompido = False

def limpar_tela():
    os.system('clear' if os.name == 'posix' else 'cls')

def mostrar_barra_progresso(mensagem="Processando"):
    """Mostra uma barra de progresso animada com spinner"""
    spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    total = 50

    for i in range(total + 1):
        if download_interrompido:
            break

        progresso = int((i / total) * 100)
        barra = '█' * i + '-' * (total - i)
        frame = spinner[i % len(spinner)]

        sys.stdout.write(f"\r\033[36m{mensagem} {frame}\033[0m [{barra}] {progresso}%  ")
        sys.stdout.flush()
        time.sleep(0.05)

    sys.stdout.write("\r" + " " * 80 + "\r")
    sys.stdout.flush()

class ProgressoItem:
    """Armazena os dados de progresso de cada item da playlist"""
    def __init__(self, index, total, titulo):
        self.index = index      # Número do item (ex: 3/25)
        self.total = total      # Total de itens na playlist
        self.titulo = titulo    # Título do vídeo/música
        self.progresso = 0      # Porcentagem (0-100)
        self.completo = False   # Se o download foi finalizado

def mostrar_spinner():
    """Retorna um caractere do spinner animado para usar nas barras"""
    spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    return spinner[int(time.time() * 10) % len(spinner)]

def mostrar_progresso_musica(item, total, titulo, progresso, spinner_char):
    """Mostra o progresso individual de cada música com barra animada"""
    # Limita o tamanho do título
    titulo_curto = (titulo[:25] + '...') if len(titulo) > 28 else titulo

    # Configurações da barra
    barra_len = 20
    blocos_cheios = int(progresso * barra_len / 100)

    # Caracteres de preenchimento suave (corrigido o índice)
    preenchimento = ['▏', '▎', '▍', '▌', '▋', '▊', '▉', '█']
    char_extra = preenchimento[int((progresso % 5) * (len(preenchimento)-1))] if progresso < 100 else ''

    # Constrói a barra
    barra = '█' * blocos_cheios + char_extra
    barra = barra.ljust(barra_len, ' ')

    # Mostra o progresso
    sys.stdout.write("\r\033[K")  # Limpa a linha
    if progresso >= 100:
        print(f"\033[1;32m[✓] {titulo_curto.ljust(30)}\033[0m")
    else:
        sys.stdout.write(
            f"\033[1;36m{spinner_char} [{item:03d}/{total:03d}] {titulo_curto.ljust(25)} "
            f"[{barra}] {progresso:5.1f}%\033[0m"
        )
    sys.stdout.flush()

def executar_comando_silencioso(comando):
    """Executa um comando sem mostrar a saída"""
    try:
        subprocess.run(comando, shell=True, check=True,
                      stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def verificar_e_configurar_ambiente():
    """Verifica e configura todo o ambiente necessário"""
    global PASTA_DOWNLOADS

    print("\033[1;34m[•] Configurando ambiente...\033[0m")

    # Verifica se está no Termux
    is_termux = 'com.termux' in HOME

    # Configura caminhos de armazenamento
    if is_termux:
        # Tenta acessar o armazenamento externo
        storage_paths = [
            '/storage/emulated/0/WolfVideos',
            '/sdcard/WolfVideos',
            os.path.join(HOME, 'storage/shared/WolfVideos')
        ]

        for path in storage_paths:
            try:
                os.makedirs(path, exist_ok=True)
                if os.access(path, os.W_OK):
                    PASTA_DOWNLOADS = path
                    break
            except (PermissionError, OSError):
                continue

        # Fallback para pasta interna se o armazenamento externo falhar
        if PASTA_DOWNLOADS == "/sdcard/WolfVideos":
            PASTA_DOWNLOADS = os.path.join(HOME, "WolfVideos")
            os.makedirs(PASTA_DOWNLOADS, exist_ok=True)
            print("\033[1;33m[!] Usando pasta interna por falta de permissões\033[0m")

        # Configura PATH do Termux
        termux_paths = [
            "/data/data/com.termux/files/usr/bin",
            "/data/data/com.termux/files/home/.local/bin"
        ]

        for path in termux_paths:
            if path not in os.environ["PATH"] and os.path.exists(path):
                os.environ["PATH"] += f":{path}"

    print(f"\033[1;32m[✓] Pasta de downloads: {PASTA_DOWNLOADS}\033[0m")

    # Instala dependências
    if not instalar_dependencias_auto():
        print("\033[1;31m[!] Falha na instalação das dependências\033[0m")
        sys.exit(1)

    # Configura cookies
    criar_cookies()

    # Atualiza cookies se necessário
    if ATUALIZAR_COOKIES_AUTO:
        atualizar_cookies()

    # Verifica permissões
    try:
        test_file = os.path.join(PASTA_DOWNLOADS, ".test_permission")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
    except Exception as e:
        print(f"\033[1;31m[!] Erro de permissão na pasta: {e}\033[0m")
        print("\033[1;33m[!] Execute no Termux: termux-setup-storage\033[0m")
        sys.exit(1)

def mostrar_menu_config():
    global ATUALIZAR_COOKIES_AUTO
    while True:
        limpar_tela()
        print("""\033[1;36m
╔════════════════════════════════════════╗
║           ⚙️  CONFIGURAÇÕES             ║
╠════════════════════════════════════════╣
║ 1. {} Atualização automática de cookies║
║ 2. ⚡ Instalar todas as dependências   ║
║ 0. 🔙 Voltar ao menu principal         ║
╚════════════════════════════════════════╝
\033[0m""".format("✅" if ATUALIZAR_COOKIES_AUTO else "❌"))

        opcao = input("\n\033[1;36m⚙️ Escolha uma opção: \033[0m").strip()

        if opcao == "0":
            break
        elif opcao == "1":
            ATUALIZAR_COOKIES_AUTO = not ATUALIZAR_COOKIES_AUTO
            status = "ativada" if ATUALIZAR_COOKIES_AUTO else "desativada"
            print(f"\033[1;32m[✓] Atualização automática {status}\033[0m")
            time.sleep(1)
        elif opcao == "2":
            instalar_dependencias_auto()
            input("\n\033[1;36mPressione Enter para continuar...\033[0m")
        else:
            print("\033[1;31m[!] Opção inválida\033[0m")
            time.sleep(1)

def instalar_dependencias_auto():
    """Instala automaticamente todas as dependências necessárias"""
    print("\033[1;34m[•] Verificando dependências...\033[0m")
    mostrar_barra_progresso("Verificando")

    try:
        # Verifica se está no Termux
        is_termux = 'com.termux' in HOME

        # Lista de pacotes básicos
        basic_packages = ["python", "ffmpeg", "libxml2", "libxslt", "binutils", "wget", "git", "aria2"]

        if is_termux:
            # Tentativa de desbloquear o apt
            executar_comando_silencioso("rm -f /data/data/com.termux/files/usr/var/lib/apt/lists/lock")
            executar_comando_silencioso("rm -f /data/data/com.termux/files/usr/var/cache/apt/archives/lock")

            # Atualizar pacotes
            if not executar_comando_silencioso("pkg update -y"):
                executar_comando_silencioso("apt update -y")

            # Instala pacotes essenciais (incluindo aria2 para downloads rápidos)
            for pkg in basic_packages:
                if not shutil.which(pkg.split()[0]):  # Pega apenas o primeiro comando
                    executar_comando_silencioso(f"pkg install -y {pkg}")

            # Instala pip se não existir
            if not shutil.which("pip"):
                executar_comando_silencioso("pkg install -y python-pip")

        else:
            # Comandos para Linux tradicional
            executar_comando_silencioso("sudo apt update -y")
            executar_comando_silencioso("sudo apt install -y python3 python3-pip ffmpeg wget aria2")

        # Instala/atualiza pacotes Python (yt-dlp e requests)
        pip_packages = ["yt-dlp", "requests"]
        for pkg in pip_packages:
            executar_comando_silencioso(f"{sys.executable} -m pip install --user --upgrade {pkg}")

        # Garante que o yt-dlp está acessível
        if not shutil.which("yt-dlp"):
            ytdlp_path = os.path.join(TERMUX_PATH, "yt-dlp")
            if not os.path.exists(TERMUX_PATH):
                os.makedirs(TERMUX_PATH, exist_ok=True)
            executar_comando_silencioso(f"ln -s {HOME}/.local/bin/yt-dlp {ytdlp_path}")

        print("\033[1;32m[✓] Dependências instaladas/atualizadas!\033[0m")
        return True
    except Exception as e:
        print(f"\033[1;31m[!] Erro durante instalação: {e}\033[0m")
        return False

def baixar_conteudo(link, formato='mp4', qualidade=None, params_extra=None):
    """Função de download com barra de progresso em tempo real e nome do arquivo"""
    global download_interrompido, PASTA_DOWNLOADS

    # Verifica se o yt-dlp está instalado
    ytdlp_path = None
    possible_paths = [
        shutil.which("yt-dlp"),
        os.path.join(HOME, ".local/bin/yt-dlp"),
        "/data/data/com.termux/files/usr/bin/yt-dlp"
    ]

    for path in possible_paths:
        if path and os.path.exists(path):
            ytdlp_path = path
            break

    if not ytdlp_path:
        print("\033[1;31m[!] yt-dlp não encontrado. Use a opção 9 para instalar.\033[0m")
        return False

    output_template = f'"{PASTA_DOWNLOADS}/%(title)s.%(ext)s"'

    # Obtém o título do vídeo
    titulo = obter_titulo_video(link)
    if titulo:
        print(f"\n\033[1;34m[•] Baixando: {titulo}\033[0m")

    # Configura o comando base
    base_cmd = f'{ytdlp_path} --newline --user-agent "{USER_AGENT}" --cookies "{ARQUIVO_COOKIES}"'

    # Adiciona aria2c se estiver disponível
    aria2_path = shutil.which("aria2c")
    if aria2_path:
        base_cmd += f" --downloader {aria2_path} --external-downloader-args '-x 16 -k 1M'"
        print("\033[1;33m[⚡] Usando aria2c para download acelerado\033[0m")

    # Monta o comando final
    if params_extra:
        comando = f'{base_cmd} {params_extra} -o {output_template} "{link}"'
    elif formato == 'mp3':
        comando = f'{base_cmd} -x --audio-format mp3 --audio-quality 0 -o {output_template} "{link}"'
    elif qualidade:
        comando = f'{base_cmd} -f "{qualidade}+bestaudio" --merge-output-format {formato} -o {output_template} "{link}"'
    else:
        comando = f'{base_cmd} -f best -o {output_template} "{link}"'

    # Configura o processo
    processo = subprocess.Popen(
        comando,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
        universal_newlines=True
    )

    queue = Queue()

    def enqueue_output(out, queue):
        for line in iter(out.readline, ''):
            queue.put(line)
        out.close()

    Thread(target=enqueue_output, args=(processo.stdout, queue)).start()

    spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    progresso = 0
    i = 0
    ultimo_progresso = 0

    try:
        while True:
            if download_interrompido:
                processo.terminate()
                break

            try:
                line = queue.get_nowait()
                # Padrões alternativos para captura de progresso
                match = (re.search(r'(\d+\.\d+)%', line) or
                        re.search(r'(\d+)%', line) or
                        re.search(r'\[download\]\s+(\d+\.?\d*)%', line))
                if match:
                    progresso = float(match.group(1))
                    ultimo_progresso = progresso
            except Empty:
                progresso = ultimo_progresso

            # Fallback para terminais sem suporte a ANSI
            if not sys.stdout.isatty():
                print(f"Progresso: {progresso:.1f}%")
                time.sleep(0.5)
                continue

            barra_completa = 50
            barra_preenchida = int(progresso * barra_completa / 100)
            barra = '█' * barra_preenchida + '-' * (barra_completa - barra_preenchida)

            sys.stdout.write(f"\r\033[36mBaixando {spinner[i % len(spinner)]} [{barra}] {progresso:.1f}%\033[0m")
            sys.stdout.flush()
            i += 1

            if processo.poll() is not None:
                break

            time.sleep(0.1)

    except KeyboardInterrupt:
        processo.terminate()
        download_interrompido = True
        sys.stdout.write("\n\033[1;31m[!] Download cancelado\033[0m\n")
        return False

    # Limpa a barra de progresso
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()

    return processo.returncode == 0

def criar_cookies():
    """Cria arquivo de cookies padrão se não existir"""
    try:
        if not os.path.exists(ARQUIVO_COOKIES):
            cookies_padrao = """# Netscape HTTP Cookie File
.xvideos.com    TRUE    /       FALSE   1735689600      ts      1
.xvideos.com    TRUE    /       FALSE   1735689600      platform      pc
.xvideos.com    TRUE    /       FALSE   1735689600      hash    5a8d9f8e7c6b5a4d3e2f1
"""
            with open(ARQUIVO_COOKIES, 'w') as f:
                f.write(cookies_padrao)
    except PermissionError:
        alt_cookies = os.path.join(HOME, ".cookies.txt")
        with open(alt_cookies, 'w') as f:
            f.write(cookies_padrao)
        return alt_cookies
    return ARQUIVO_COOKIES

def atualizar_cookies():
    """Atualiza cookies a partir da URL"""
    try:
        print("\033[1;34m[•] Atualizando cookies...\033[0m")
        mostrar_barra_progresso("Baixando")

        headers= {'User-Agent': USER_AGENT}
        response = requests.get(URL_ATUALIZACAO_COOKIES, headers=headers, timeout=10)

        if response.status_code == 200:
            with open(ARQUIVO_COOKIES, 'w') as f:
                f.write(response.text)
            print("\033[1;32m[✓] Cookies atualizados!\033[0m")
    except Exception:
        print("\033[1;31m[!] Erro ao atualizar cookies\033[0m")

def mostrar_banner():
    print("""\033[1;36m
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣶⠶⢦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣾⠁⠀⠸⠛⢳⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣸⠃⠀⠀⠀⠀⣿⠹⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣰⠃⠀⠀⠀⠀⠀⣿⠀⢿⠀⣴⠟⠷⣆⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣴⠃⠀⠀⠀⠀⢀⣤⡟⠀⢸⣿⠃⠀⠀⠘⣷⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡾⠁⠀⠀⠀⠀⠀⣸⡿⠿⠟⢿⡏⠀⠀⠀⢀⣿⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣤⣾ ⠀⠀⠀⠀⠀⠀⠀⢸⡇⠀⠀⣼⡇⠀⠀⠀⣸⡏⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⡾⠛⡋⠉⣩⡇⠀⠀⠀⠀⠀⠀⠀⠀⠘⣷⣰⠟⠋⠁⠀⠀⢠⡟⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣰⠏⢠⡞⣱⣿⠟⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⠟⠀⠀⠀⠀⠀⣾⠃⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡴⠃⢀⣿⢁⣿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠀⠀⠀⠀⣠⢰⣿⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀ ⠀⠀⠀⢠⡾⠁⠀⢸⣿⣿⢀⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⠀⠀⢀⣶⣾⡇⢸⣧⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣰⡿⠀⠀⠀⢸⣿⣿⣾⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣏⣠⢰⢻⡟⢃⡿⡟⣿⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⢰⣿⡇⠀⠀⠀⠀⠁⢿⠹⣿⣄⠀⠀⠀⢀⠀⠀⠀⠀⢺⠏⣿⣿⠼⠁⠈⠰⠃⣿⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⢀⣿⡟⠃⠀⠈⢻⣷⣄⠈⠁⣿⣿⡇⠀⠀⠈⣧⠀⠀⠀⠘⣠⠟⠁⠀⠀⠀⠀⠀⢻⡇⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⢀⣾⠟⠀⠀⣴⠀⠀⣿⡿⠀⠸⠋⢸⣿⣧⡐⣦⣸⡆⠀⠀⠈⠁⠀⠀⠀⠀⠀⠀⠀⠘⣿⡀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⣠⡿⠃⠀⣀⣴⣿⡆⢀⣿⠃⠀⠀⠀⣸⠟⢹⣷⣿⡿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠹⣧⠀⠀⠀⠀⠀⠀
⠀⠀⠀⣀⣤⣾⡏⠛⠻⠿⣿⣿⣿⠁⣼⠇⠀⠀⠀⠀⠁⠀⢸⣿⠙⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠹⣇⠀⠀⠀⠀⠀
⠲⢾⠛⣿⣿⣿⣇⢀⣠⣴⣿⡿⢁⣼⣿⣀⠀⠀⠀⠀⠀⠀⠈⢿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣆⠀⠀⠀⠀
⠀⠀⠉⠙⠛⠻⣿⣷⣶⣿⣷⠾⣿⣵⣿⡏⠀⠀⠀⠀⠀⠀⠀⠀⠙⠀⠀⠀⠀⠀⠀⠀⢤⡀⠀⠀⠀⠀⠀⠀⠀⡀⢿⡆⠀⠀⠀
⠀⠀⠀⠀⠀⣰⣿⡟⣴⠀⠀⠉⠉⠁⢿⡇⣴⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⡆⠀⠀⠀⠀⣴⠀⣿⣿⣿⠀⠀⠀
⠀⠀⠀⠀⢠⣿⠿⣿⣿⢠⠇⠀⠀⠀⢸⣿⢿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣤⣀⠀⠀⢸⣿⡄⠀⠀⣼⣿⣇⢹⡟⢿⡇⠀⠀
⠀⠀⠀⠀⣿⠃⣠⣿⣿⣿⠀⠀⠀⠀⠀⢻⡈⢿⣆⠀⢳⡀⠀⢠⠀⠀⠀⠀⠀⢸⣿⣦⠀⣸⠿⣷⡀⠀⣿⣿⢿⣾⣿⠸⠇⠀⠀
⠀⠀⠀⠀⠋⣰⣿⣿⣿⣿⡀⢰⡀⠀⠀⠀⠀⠈⢻⣆⣼⣷⣄⠈⢷⡀⠀⠀⠀⢸⣿⢿⣶⠟⠀⠙⣷⣼⣿⣿⡄⠻⣿⣧⡀⠀⠀
⠀⠀⠀⠀⠀⣿⣿⣿⣿⣿⣧⡿⠀⠀⠀⠀⠀⠀⠀⠙⢿⡄⠻⣷⣼⣿⣦⡀⠀⣼⠇⠸⠋⠀⠀⠀⠈⠻⣿⣿⣷⡀⠈⠻⣷⡀⠀
⠀⠀⠀⠀⠀⣿⣼⡿⢻⣿⡿⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠀⠈⠻⣷⡙⣿⣶⡿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢿⣷⢠⣀⠘⣷⡀
⠀⠀⠀⠀⠀⠀⣿⠇⣾⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠈⠛⢿⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢿⠀⢻⣷⣾⡇
⠀⠀⠀⠀⠀⠀⣿⢠⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠓⠀⠀⠀⠀⠀⠀⠀⠀⠀⠸⠀⢈⣿⡹⣷
⠀⠀⠀⠀⠀⠀⠈⠀⠻⠿⠿⠆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣸⣿⡇⠉


██╗    ██╗ ██████╗ ██╗     ███████╗
██║    ██║██╔═══██╗██║     ██╔════╝
██║ █╗ ██║██║   ██║██║     █████╗
██║███╗██║██║   ██║██║     ██╔══╝
╚███╔███╔╝╚██████╔╝███████╗██║
 ╚══╝╚══╝  ╚═════╝ ╚══════╝╚═╝

██╗   ██╗██╗██████╗ ███████╗ ██████╗ ███████╗
██║   ██║██║██╔══██╗██╔════╝██╔═══██╗██╔════╝
██║   ██║██║██║  ██║█████╗  ██║   ██║███████╗
╚██╗ ██╔╝██║██║  ██║██╔══╝  ██║   ██║╚════██║
 ╚████╔╝ ██║██████╔╝███████╗╚██████╔╝███████║
  ╚═══╝  ╚═╝╚═════╝ ╚══════╝ ╚═════╝ ╚══════╝


 \033[1;32m_______________________________________________
 | insta:jottap_62 • by jottap_62 • v8.5 • Wolf |
 ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
\033[1;33m• Recursos Premium:
  ✔ Download de vídeos 4K/1080p
  ✔ Conversão para MP3 com qualidade de estúdio
  ✔ Bypass de paywalls e restrições
  ✔ Sistema de cookies automático
  ✔ Player integrado com pré-visualização
  ✔ Suporte a múltiplas plataformas\033[0m""")

def mostrar_menu_video_qualidade():
    print("""\033[1;36m
╔════════════════════════════════════════╗
║        📽  VIDEO QUALITY OPTIONS        ║
╠════════════════════════════════════════╣
║ 1. 🎯 Best quality (4K if available)   ║
║ 2. 🖥  1080p HD                         ║
║ 3. 💻  720p HD                         ║
║ 4. 📱  480p                            ║
║ 5. 📼  360p                            ║
║ 0. 🚪 Voltar                           ║
╚════════════════════════════════════════╝
\033[0m""")

def mostrar_menu_audio_formatos():
    print("""\033[1;36m
╔════════════════════════════════════════╗
║        🎵 AUDIO FORMAT OPTIONS         ║
╠════════════════════════════════════════╣
║ 1. 🎧 MP3 (High quality 320kbps)       ║
║ 2. 🎵 AAC (High quality)               ║
║ 3. 🎼 FLAC (Lossless)                  ║
║ 4. 🎤 M4A (YouTube default)            ║
║ 5. 🎶 OPUS (Efficient)                 ║
║ 6. 💿 MP3 with cover art               ║
║ 0. 🚪 Voltar                           ║
╚════════════════════════════════════════╝
\033[0m""")

def listar_formatos(link):
    """Lista os formatos disponíveis para download"""
    print("\033[1;36m[•] Listando formatos disponíveis...\033[0m")
    mostrar_barra_progresso("Analisando")

    # Executa o comando para listar formatos
    executar_comando_silencioso(f'yt-dlp --cookies "{ARQUIVO_COOKIES}" -F "{link}"')

    while True:
        limpar_tela()
        mostrar_menu_video_qualidade()
        opcao = input("\n\033[1;36m🎬 Escolha uma opção [0-5]: \033[0m").strip()

        if opcao == "0":
            break
        elif opcao in FORMATOS_VIDEO:
            print("\033[1;33m[•] Iniciando download...\033[0m")

            # Obtém o título antes de começar
            titulo = obter_titulo_video(link)
            if titulo:
                print(f"\033[1;34m[•] Baixando: {titulo}\033[0m")

            if baixar_conteudo(link, 'mp4', FORMATOS_VIDEO[opcao]['code']):
                # Limpa a linha da barra de progresso
                sys.stdout.write("\r\033[K")
                sys.stdout.flush()
                print(f"\033[1;32m[✓] Concluído! Arquivo em: {PASTA_DOWNLOADS}\033[0m")
            break
        else:
            print("\033[1;31m[!] Opção inválida\033[0m")
            time.sleep(1)

print("\033[1;33m[⚡] Usando aria2c para download acelerado\033[0m")

def baixar_playlist(link, tipo='video'):
    """Baixa playlists com barras de progresso individuais"""
    global download_interrompido

    print("\033[1;34m[•] Obtendo informações da playlist...\033[0m")
    mostrar_barra_progresso("Analisando")

    try:
        # Obtém todos os itens primeiro para ter índices corretos
        cmd_info = f'yt-dlp --playlist-items 1-500 --flat-playlist --print "%(playlist_index)s %(title)s" "{link}"'
        resultado = subprocess.run(cmd_info, shell=True, capture_output=True, text=True)
        itens = [linha.split(' ', 1) for linha in resultado.stdout.strip().split('\n') if linha]
        total_itens = len(itens)
        titulos = {int(idx): titulo.strip() for idx, titulo in itens}
    except Exception as e:
        print(f"\033[1;31m[!] Erro: {str(e)}\033[0m")
        return False

    if total_itens == 0:
        print("\033[1;31m[!] Playlist vazia ou não encontrada\033[0m")
        return False

    print(f"\033[1;32m[✓] Encontradas {total_itens} músicas\033[0m")

    # Verifica arquivos já baixados
    padrao_arquivo = re.compile(r'^(\d+) - .+\.(mp3|mp4|m4a|flac|opus)$')
    itens_baixados = set()

    try:
        for arquivo in os.listdir(PASTA_DOWNLOADS):
            match = padrao_arquivo.match(arquivo)
            if match:
                itens_baixados.add(int(match.group(1)))
    except Exception as e:
        print(f"\033[1;33m[!] Erro ao verificar arquivos existentes: {e}\033[0m")

    # Cria lista de itens pendentes
    itens_pendentes = [str(idx) for idx in titulos.keys() if idx not in itens_baixados]

    if not itens_pendentes:
        print("\033[1;32m[✓] Todos os itens já foram baixados anteriormente!\033[0m")
        return True

    # Configura o comando base
    base_cmd = f'yt-dlp --newline --user-agent "{USER_AGENT}" --cookies "{ARQUIVO_COOKIES}"'
    if shutil.which("aria2c"):
        base_cmd += " --downloader aria2c --external-downloader-args '-x 16 -k 1M'"
        print("\033[1;33m[⚡] Usando download acelerado\033[0m")

    # Configura qualidade/formato
    if tipo == 'video':
        mostrar_menu_video_qualidade()
        opcao = input("\n\033[1;36m🎬 Qualidade (1-5): \033[0m").strip()
        qualidade = FORMATOS_VIDEO.get(opcao, {}).get('code', 'best')
        cmd = f'{base_cmd} -f "{qualidade}+bestaudio" --merge-output-format mp4 -o "{PASTA_DOWNLOADS}/%(playlist_index)s - %(title)s.%(ext)s" --playlist-items {",".join(itens_pendentes)} "{link}"'
    else:
        mostrar_menu_audio_formatos()
        opcao = input("\n\033[1;36m🎵 Formato (1-6): \033[0m").strip()
        formato = FORMATOS_AUDIO.get(opcao, FORMATOS_AUDIO['1'])
        cmd = f'{base_cmd} {formato["params"]} -o "{PASTA_DOWNLOADS}/%(playlist_index)s - %(title)s.%(ext)s" --playlist-items {",".join(itens_pendentes)} "{link}"'

    # Prepara os itens de progresso (apenas para os pendentes)
    itens_progresso = [ProgressoItem(idx, total_itens, titulos[idx]) for idx in titulos.keys() if idx not in itens_baixados]
    item_atual = None

    # Salva estado para possível continuação
    try:
        with open(ARQUIVO_DOWNLOADS_PARCIAL, 'w') as f:
            f.write(f"{link}\n{tipo}\n{opcao}")
    except IOError as e:
        print(f"\033[1;31m[!] Erro ao salvar estado do download: {e}\033[0m")

    processo = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    try:
        while True:
            if download_interrompido:
                processo.terminate()
                break

            line = processo.stdout.readline()
            if not line:
                break

            # Detecta novo item
            if "[download] Downloading item" in line:
                idx = int(line.split()[3])
                item_atual = next((i for i in itens_progresso if i.index == idx), None)
                if item_atual:
                    item_atual.progresso = 0
                    item_atual.completo = False

            # Atualiza progresso
            elif "[download]" in line and "%" in line:
                if item_atual:
                    match = re.search(r'(\d+\.?\d*)%', line)
                    if match:
                        item_atual.progresso = float(match.group(1))

            # Marca como completo
            elif "[download] 100%" in line and item_atual:
                item_atual.progresso = 100
                item_atual.completo = True

            # Atualiza a exibição
            if item_atual:
                mostrar_progresso_playlist(item_atual.index, total_itens, item_atual.titulo, item_atual.progresso, int(time.time() * 10) % 10)

    except KeyboardInterrupt:
        processo.terminate()
        download_interrompido = True
        print("\n\033[1;31m[!] Download interrompido\033[0m")
        return False

    if processo.returncode == 0 and os.path.exists(ARQUIVO_DOWNLOADS_PARCIAL):
        os.remove(ARQUIVO_DOWNLOADS_PARCIAL)
        print("\033[1;32m[✓] Download completo!\033[0m")
    return True

def mostrar_progresso_playlist(item, total, titulo, progresso, spinner_idx):
    """
    Versão final com otimização para playlists longas (+50 itens)
    e todas as melhorias anteriores incorporadas
    """
    try:
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        barra_len = 20

        # Configuração adaptativa de tamanho de título
        if total > 50:  # Otimização para playlists muito longas
            max_titulo_len = 15
            ellipsis = '...'
        elif shutil.which('termux-api'):  # Dispositivos móveis
            max_titulo_len = 22
            ellipsis = '..'
        else:  # Desktop/terminal grande
            max_titulo_len = 28
            ellipsis = '..'

        # Formatação do título com truncagem inteligente
        if len(titulo) > max_titulo_len:
            titulo_curto = titulo[:max_titulo_len-len(ellipsis)] + ellipsis
        else:
            titulo_curto = titulo
        titulo_formatado = titulo_curto.ljust(max_titulo_len)

        # Cálculo preciso da barra de progresso
        progresso_clamped = min(100.0, max(0.0, float(progresso)))
        progresso_frac = progresso_clamped / 100.0
        blocos_cheios = int(progresso_frac * barra_len)
        resto = (progresso_frac * barra_len) - blocos_cheios

        # Preenchimento parcial suave
        chars_parciais = ['', '▏', '▎', '▍', '▌', '▋', '▊', '▉']
        parcial_idx = min(7, int(resto * 8))
        parcial = chars_parciais[parcial_idx] if progresso_clamped < 100 else ''

        # Construção da barra
        barra = ('█' * blocos_cheios) + parcial
        barra = barra.ljust(barra_len, ' ')

        # Renderização otimizada
        if progresso_clamped >= 100.0:
            sys.stdout.write("\r\033[K")  # Limpa a linha
            linha_concluido = (f"\033[1;32m[✓] [{item:02d}/{total:02d}] "
                             f"{titulo_formatado} [{'█'*barra_len}] 100%\033[0m\n")
            sys.stdout.write(linha_concluido)
        else:
            linha = (f"\r\033[1;36m{spinner[spinner_idx % len(spinner)]} "
                    f"[{item:02d}/{total:02d}] {titulo_formatado} "
                    f"[{barra}] {progresso_clamped:5.1f}%\033[0m")

            sys.stdout.write(linha + '\033[?25l')  # Esconde cursor durante atualização
            sys.stdout.flush()

    except Exception:
        # Fallback silencioso
        try:
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()
        except:
            pass

    # Garante que o cursor volta ao normal
    finally:
        if 'linha' in locals() and progresso_clamped < 100:
            sys.stdout.write('\033[?25h')  # Restaura cursor

def baixar_spotify_deezer():
    print("\033[1;36m[•] Baixar de Spotify ou Deezer\033[0m")
    link = input("\n\033[1;36m🔗 Digite a URL da música/playlist: \033[0m").strip()
    if not link.startswith(("http://", "https://")):
        print("\033[1;31m[!] URL inválida\033[0m")
        return

    print("\033[1;33m[•] Iniciando download com spotDL...\033[0m")
    comando = f"spotdl download \"{link}\" --output \"{PASTA_DOWNLOADS}/%(title)s.%(ext)s\""
    try:
        subprocess.run(comando, shell=True, check=True)
        print(f"\033[1;32m[✓] Download concluído! Arquivos em: {PASTA_DOWNLOADS}\033[0m")
    except subprocess.CalledProcessError:
        print("\033[1;31m[!] Falha ao baixar com spotDL\033[0m")

def baixar_multiplas_urls(tipo='video'):
    """Baixa múltiplas URLs de uma vez"""
    print("\033[1;36m[•] Modo múltiplas URLs (CTRL+D para finalizar)\033[0m")
    print("\033[1;33m[•] Cole as URLs uma por linha:\033[0m")

    urls = []
    try:
        while True:
            url = input().strip()
            if url.startswith(('http://', 'https://')):
                urls.append(url)
            elif url:
                print("\033[1;31m[!] URL inválida\033[0m")
    except EOFError:
        pass

    if not urls:
        print("\033[1;31m[!] Nenhuma URL fornecida\033[0m")
        return

    if tipo == 'video':
        mostrar_menu_video_qualidade()
        opcao = input("\n\033[1;36m🎬 Escolha a qualidade [1-5]: \033[0m").strip()
        qualidade = FORMATOS_VIDEO[opcao]['code'] if opcao in FORMATOS_VIDEO else 'best'
    else:
        mostrar_menu_audio_formatos()
        opcao = input("\n\033[1;36m🎵 Escolha o formato [1-6]: \033[0m").strip()
        formato = FORMATOS_AUDIO[opcao] if opcao in FORMATOS_AUDIO else FORMATOS_AUDIO['1']

    for i, url in enumerate(urls, 1):
        print(f"\n\033[1;35m[•] Baixando URL {i}/{len(urls)}\033[0m")
        mostrar_barra_progresso("Processando")

        if tipo == 'video':
            baixar_conteudo(url, 'mp4', qualidade)
        else:
            baixar_conteudo(url, formato['code'], None, formato['params'])

def obter_titulo_video(url):
    """Obtém o título do vídeo usando yt-dlp"""
    try:
        comando = f'yt-dlp --get-title --no-warnings "{url}"'
        resultado = subprocess.run(comando, shell=True, capture_output=True, text=True)
        if resultado.returncode == 0:
            return resultado.stdout.strip()
        return None
    except Exception:
        return None

def sinal_handler(sig, frame):
    """Lida com sinais de interrupção salvando o estado"""
    global download_interrompido
    download_interrompido = True

    # Verifica se há um download em andamento
    if os.path.exists(ARQUIVO_DOWNLOADS_PARCIAL):
        with open(ARQUIVO_DOWNLOADS_PARCIAL, 'r') as f:
            link = f.readline().strip()
            print("\n\033[1;33m[!] Recebido sinal de interrupção - Estado salvo\033[0m")
            print(f"\033[1;34m[•] Você pode continuar este download depois: {link}\033[0m")

    sys.exit(0)

def continuar_download_playlist():
    """Continua um download de playlist interrompido com progresso individual"""
    global download_interrompido

    if not os.path.exists(ARQUIVO_DOWNLOADS_PARCIAL):
        print("\033[1;31m[!] Nenhum download parcial encontrado para continuar\033[0m")
        return False

    try:
        with open(ARQUIVO_DOWNLOADS_PARCIAL, 'r') as f:
            linhas = f.readlines()
            if len(linhas) < 3:
                print("\033[1;31m[!] Arquivo de download parcial corrompido\033[0m")
                return False

            link = linhas[0].strip()
            tipo = linhas[1].strip()
            opcao = linhas[2].strip()

        print("\033[1;33m[•] Continuando download interrompido...\033[0m")
        mostrar_barra_progresso("Recuperando estado")

        # Obtém informações atualizadas da playlist
        cmd_info = f'yt-dlp --playlist-items 1-500 --flat-playlist --print "%(playlist_index)s %(title)s" "{link}"'
        resultado = subprocess.run(cmd_info, shell=True, capture_output=True, text=True)
        itens = [linha.split(' ', 1) for linha in resultado.stdout.strip().split('\n') if linha]
        total_itens = len(itens)
        titulos = {int(idx): titulo.strip() for idx, titulo in itens}

        # Configura o comando base com a opção salva
        base_cmd = f'yt-dlp --newline --user-agent "{USER_AGENT}" --cookies "{ARQUIVO_COOKIES}"'
        if shutil.which("aria2c"):
            base_cmd += " --downloader aria2c --external-downloader-args '-x 16 -k 1M'"

        if tipo == 'video':
            qualidade = FORMATOS_VIDEO.get(opcao, {}).get('code', 'best')
            cmd = f'{base_cmd} -f "{qualidade}+bestaudio" --merge-output-format mp4 -o "{PASTA_DOWNLOADS}/%(playlist_index)s - %(title)s.%(ext)s" "{link}"'
        else:
            formato = FORMATOS_AUDIO.get(opcao, FORMATOS_AUDIO['1'])
            cmd = f'{base_cmd} {formato["params"]} -o "{PASTA_DOWNLOADS}/%(playlist_index)s - %(title)s.%(ext)s" "{link}"'

        # Prepara itens de progresso
        itens_progresso = [ProgressoItem(idx, total_itens, titulos[idx]) for idx in titulos.keys()]
        processo = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

        try:
            item_atual = None
            while True:
                if download_interrompido:
                    processo.terminate()
                    break

                line = processo.stdout.readline()
                if not line:
                    break

                # Atualiza progresso (mesma lógica da função original)
                if "[download] Downloading item" in line:
                    idx = int(line.split()[3])
                    item_atual = next((i for i in itens_progresso if i.index == idx), None)

                elif "[download]" in line and "%" in line and item_atual:
                    match = re.search(r'(\d+\.?\d*)%', line)
                    if match:
                        item_atual.progresso = float(match.group(1))
                        mostrar_progresso_playlist(
                            item_atual.index,
                            total_itens,
                            item_atual.titulo,
                            item_atual.progresso,
                            int(time.time() * 10) % 10
                        )

                elif "[download] 100%" in line and item_atual:
                    item_atual.progresso = 100
                    mostrar_progresso_playlist(
                        item_atual.index,
                        total_itens,
                        item_atual.titulo,
                        item_atual.progresso,
                        int(time.time() * 10) % 10
                    )

        except KeyboardInterrupt:
            processo.terminate()
            download_interrompido = True
            print("\n\033[1;31m[!] Download interrompido\033[0m")
            return False

        if processo.returncode == 0:
            if os.path.exists(ARQUIVO_DOWNLOADS_PARCIAL):
                os.remove(ARQUIVO_DOWNLOADS_PARCIAL)
            print("\033[1;32m[✓] Download completo!\033[0m")
            return True

    except Exception as e:
        print(f"\033[1;31m[!] Erro ao continuar: {str(e)}\033[0m")
        return False

def mostrar_menu_principal():
    print("""\033[1;36m
╔════════════════════════════════════════╗
║    🎬 WOLF VIDEO DOWNLOADER PREMIUM    ║
╠════════════════════════════════════════╣
║ 1. 🎥 Baixar vídeo (melhor qualidade)  ║
║ 2. 📊 Escolher qualidade específica    ║
║ 3. 🎧 Converter para áudio             ║
║ 4. 📋 Listar formatos disponíveis      ║
║ 5. 📺 Baixar playlist de vídeos        ║
║ 6. 🎵 Baixar playlist de áudios        ║
║ 7. 📂 Baixar múltiplos vídeos          ║
║ 8. 🎶 Baixar múltiplos áudios          ║
║ 9. 🔄 Atualizar ferramentas            ║
║10. 🍪 Atualizar cookies manualmente    ║
║11. ⚙️ Configurações                     ║
║12. ⏯️ Continuar download de playlist    ║
║13. 🟢 Baixar de Spotify/Deezer         ║
║ 0. 🚪 Sair                             ║
╚════════════════════════════════════════╝
\033[0m""")

def main():
    global download_interrompido

    # Configura o handler para sinais de interrupção
    signal.signal(signal.SIGINT, sinal_handler)
    signal.signal(signal.SIGTERM, sinal_handler)

    limpar_tela()
    mostrar_banner()
    verificar_e_configurar_ambiente()

    # Verifica se há downloads parciais para continuar
   # if os.path.exists(ARQUIVO_DOWNLOADS_PARCIAL):
       # resposta = input("\033[1;33m[?] Há downloads não concluídos. Deseja continuar? [S/n]: \033[0m").strip().lower()
       # if resposta in ('s', 'sim', ''):
           # continuar_download_playlist()

    while True:
        download_interrompido = False
        mostrar_menu_principal()
        opcao = input("\n\033[1;36m✨ Escolha uma opção [0-12]: \033[0m").strip()

        if opcao == "0":
            print("\n\033[1;32m[✓] Programa encerrado👋\033[0m")
            break

        elif opcao == "1":
            link = input("\n\033[1;36m🔗 Digite a URL: \033[0m").strip()
            if not link.startswith(('http://', 'https://')):
                print("\033[1;31m[!] URL inválida\033[0m")
                continue
            print("\033[1;33m[•] Iniciando download...\033[0m")
            mostrar_barra_progresso("Baixando")
            if baixar_conteudo(link, 'mp4'):
                print(f"\033[1;32m[✓] Concluído! Arquivo em: {PASTA_DOWNLOADS}\033[0m")

        elif opcao == "2":
            link = input("\n\033[1;36m🔗 Digite a URL: \033[0m").strip()
            if not link.startswith(('http://', 'https://')):
                print("\033[1;31m[!] URL inválida\033[0m")
                continue
            listar_formatos(link)

        elif opcao == "3":
            link = input("\n\033[1;36m🔗 Digite a URL: \033[0m").strip()
            if not link.startswith(('http://', 'https://')):
                print("\033[1;31m[!] URL inválida\033[0m")
                continue
            mostrar_menu_audio_formatos()
            opcao_audio = input("\n\033[1;36m🎵 Escolha o formato [1-6]: \033[0m").strip()
            if opcao_audio in FORMATOS_AUDIO:
                formato = FORMATOS_AUDIO[opcao_audio]
                print("\033[1;33m[•] Iniciando conversão...\033[0m")
                mostrar_barra_progresso("Convertendo")
                if baixar_conteudo(link, formato['code'], None, formato['params']):
                    print(f"\033[1;32m[✓] Concluído! Arquivo em: {PASTA_DOWNLOADS}\033[0m")

        elif opcao == "4":
            link = input("\n\033[1;36m🔗 Digite a URL: \033[0m").strip()
            if not link.startswith(('http://', 'https://')):
                print("\033[1;31m[!] URL inválida\033[0m")
                continue
            listar_formatos(link)

        elif opcao == "5":
            link = input("\n\033[1;36m🔗 Digite a URL da playlist: \033[0m").strip()
            if link.startswith(('http://', 'https://')):
                baixar_playlist(link, tipo='video')
            else:
                print("\033[1;31m[!] URL inválida\033[0m")

        elif opcao == "6":
            link = input("\n\033[1;36m🔗 Digite a URL da playlist: \033[0m").strip()
            if link.startswith(('http://', 'https://')):
                baixar_playlist(link, tipo='audio')
            else:
                print("\033[1;31m[!] URL inválida\033[0m")

        elif opcao == "7":
            baixar_multiplas_urls(tipo='video')

        elif opcao == "8":
            baixar_multiplas_urls(tipo='audio')

        elif opcao == "9":
            print("\033[1;34m[•] Atualizando ferramentas...\033[0m")
            mostrar_barra_progresso("Atualizando")
            executar_comando_silencioso(f"{sys.executable} -m pip install --user --upgrade yt-dlp requests")
            print("\033[1;32m[✓] Ferramentas atualizadas!\033[0m")

        elif opcao == "10":
            atualizar_cookies()

        elif opcao == "11":
            mostrar_menu_config()

        elif opcao == "12":
            continuar_download_playlist()

        elif opcao == "13":
          baixar_spotify_deezer()

        else:
            print("\033[1;31m[!] Opção inválida\033[0m")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\033[1;31m[!] Interrompido pelo usuário\033[0m")
        sys.exit(0)
