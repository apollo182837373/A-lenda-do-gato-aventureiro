"""
GATO AVENTUREIRO - VERSAO COMPLETA (5 FASES + CHEFE FINAL)
============================================================
Feito para rodar no Pydroid 3 (Android) OU no navegador via pygbag.

COMO JOGAR NO CELULAR (Pydroid 3):
1. Abra o Pydroid 3
2. Va em "Pip", pesquise "pygame" e instale
3. (opcional) pesquise "numpy" e instale tambem -- deixa o
   carregamento dos sons bem mais rapido
4. Cole este codigo num arquivo .py e toque em Play

COMO PUBLICAR NO NAVEGADOR (pygbag):
Este arquivo ja esta pronto para o pygbag: o loop principal roda
dentro de uma funcao "async def main()" com "await asyncio.sleep(0)"
a cada quadro, que e exatamente o formato que o pygbag exige para
gerar uma versao web (WebAssembly) do jogo.

CONTROLES (TOUCH NA TELA):
- Botoes esquerda/direita (canto inferior esquerdo): mover
- Botao PULAR (canto inferior direito): pular / nadar / atacar
- Tambem funciona com teclado (setas + espaco) no PC
- Objetivo: atravessar as 5 fases e derrotar o chefe final!

AS 5 FASES:
1. CAMPO - a fase classica, grama, moedas e blocos quebraveis
2. OCEANO - fase aquatica, nade entre peixes e tubaroes
3. CEUS - plataformas de nuvem flutuantes, inimigos voadores/eletricos
4. VULCAO - pedras e lava, cuidado com o novo inimigo de lava
5. CHEFE FINAL - um TIGRE GIGANTE com barra de vida!

Cada fase tem visual, inimigos e trilha sonora proprios (todas as
musicas sao composicoes originais, geradas na hora por formulas
matematicas -- nao reproduzem nenhuma musica existente).
"""

import pygame
import sys
import math
import array
import random
import asyncio

pygame.init()

try:
    import numpy as np
    NUMPY_DISPONIVEL = True
except ImportError:
    NUMPY_DISPONIVEL = False

# ---------------------------------------------------------
# AUDIO
# ---------------------------------------------------------
TAXA_AMOSTRAGEM = 11025
SOM_ATIVADO = True
try:
    pygame.mixer.init(frequency=TAXA_AMOSTRAGEM, size=-16, channels=1, buffer=512)
except pygame.error:
    SOM_ATIVADO = False

# ---------------------------------------------------------
# TELA CHEIA
# ---------------------------------------------------------
LARGURA, ALTURA = 800, 450
VERSAO_JOGO = "v14 - pausa e musica"

MODO_SCALED = True
try:
    TELA = pygame.display.set_mode((LARGURA, ALTURA), pygame.FULLSCREEN | pygame.SCALED)
except pygame.error:
    MODO_SCALED = False
    try:
        TELA = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    except pygame.error:
        TELA = pygame.display.set_mode((LARGURA, ALTURA))

pygame.display.set_caption("Gato Aventureiro")

if MODO_SCALED:
    CANVAS = TELA
    TELA_LARGURA, TELA_ALTURA = LARGURA, ALTURA
else:
    CANVAS = pygame.Surface((LARGURA, ALTURA))
    TELA_LARGURA, TELA_ALTURA = TELA.get_size()

RELOGIO = pygame.time.Clock()
FPS = 60

GRAVIDADE = 0.95
PULO_FORCA = -17.5
VELOCIDADE = 7.5

# fisica alternativa usada na fase aquatica (fase 2)
GRAVIDADE_AGUA = 0.28
IMPULSO_NADO = -6.0
VELOCIDADE_AGUA = 5.5
QUEDA_MAX_AGUA = 6.0

# ---------------------------------------------------------
# CORES GERAIS / HUD
# ---------------------------------------------------------
BRANCO = (255, 255, 255)
PRETO = (20, 20, 20)
ROSA = (255, 180, 200)
AMARELO_MOEDA = (255, 215, 0)
AMARELO_MOEDA_ESCURO = (200, 160, 0)
VERMELHO = (230, 60, 60)
ROXO = (170, 90, 220)
ROXO_CLARO = (200, 150, 235)
CINZA_BOTAO = (60, 60, 60, 140)
BRANCO_BOTAO = (255, 255, 255, 180)
HUD_FUNDO = (30, 30, 40, 120)
VERDE_SPEED = (80, 230, 150)
LARANJA_GATO = (255, 150, 40)
LARANJA_GATO_ESCURO = (220, 110, 20)

FONTE = pygame.font.SysFont("Arial", 24, bold=True)
FONTE_GRANDE = pygame.font.SysFont("Arial", 46, bold=True)
FONTE_MEDIA = pygame.font.SysFont("Arial", 30, bold=True)
FONTE_PEQUENA = pygame.font.SysFont("Arial", 16, bold=True)
FONTE_TITULO_EVA = pygame.font.SysFont("Arial", 40, bold=True)
try:
    FONTE_LORE = pygame.font.SysFont("Georgia", 22, bold=False)
except Exception:
    FONTE_LORE = pygame.font.SysFont("Arial", 22, bold=False)


# ===========================================================
# SONS - gerados na hora com ondas simples (sem arquivos .wav)
# ===========================================================
def _forma_onda(tipo, t, freq):
    fase = (t * freq) % 1.0
    if tipo == "quadrada":
        return 1.0 if fase < 0.5 else -1.0
    if tipo == "triangular":
        return 4 * abs(fase - 0.5) - 1
    if tipo == "serra":
        return 2 * fase - 1
    return math.sin(2 * math.pi * freq * t)


def _forma_onda_vetorizada(tipo, t, freq):
    fase = np.mod(t * freq, 1.0)
    if tipo == "quadrada":
        return np.where(fase < 0.5, 1.0, -1.0)
    if tipo == "triangular":
        return 4 * np.abs(fase - 0.5) - 1
    if tipo == "serra":
        return 2 * fase - 1
    return np.sin(2 * np.pi * freq * t)


def _array_de_int16(valores_numpy):
    clampado = np.clip(valores_numpy, -32767, 32767).astype(np.int16)
    resultado = array.array("h")
    resultado.frombytes(clampado.tobytes())
    return resultado


def gerar_tom(frequencia, duracao, volume=0.5, tipo="senoide"):
    n = max(1, int(TAXA_AMOSTRAGEM * duracao))
    amp = int(32767 * volume)
    ataque = max(1, int(n * 0.05))
    solto = max(1, int(n * 0.25))

    if NUMPY_DISPONIVEL:
        t = np.arange(n, dtype=np.float64) / TAXA_AMOSTRAGEM
        onda = _forma_onda_vetorizada(tipo, t, frequencia)
        envelope = np.ones(n, dtype=np.float64)
        envelope[:ataque] = np.linspace(0.0, 1.0, ataque, endpoint=False)
        envelope[n - solto:] = np.minimum(envelope[n - solto:], np.linspace(1.0, 0.0, solto))
        return _array_de_int16(onda * amp * envelope)

    amostras = array.array("h", [0]) * n
    for i in range(n):
        t = i / TAXA_AMOSTRAGEM
        valor = _forma_onda(tipo, t, frequencia)
        if i < ataque:
            fator = i / ataque
        elif i > n - solto:
            fator = max(0.0, (n - i) / solto)
        else:
            fator = 1.0
        amostras[i] = int(valor * amp * fator)
    return amostras


def gerar_ruido(duracao, volume=0.45):
    n = max(1, int(TAXA_AMOSTRAGEM * duracao))
    amp = int(32767 * volume)

    if NUMPY_DISPONIVEL:
        fator = np.clip(1 - np.arange(n, dtype=np.float64) / n, 0.0, 1.0)
        ruido = np.random.uniform(-1.0, 1.0, n)
        return _array_de_int16(ruido * amp * fator)

    amostras = array.array("h", [0]) * n
    for i in range(n):
        fator = max(0.0, 1 - i / n)
        amostras[i] = int(random.uniform(-1, 1) * amp * fator)
    return amostras


def gerar_melodia(notas, volume=0.4, tipo="quadrada"):
    partes = []
    for freq, dur in notas:
        if freq <= 0:
            n = max(1, int(TAXA_AMOSTRAGEM * dur))
            partes.append(array.array("h", [0]) * n)
        else:
            partes.append(gerar_tom(freq, dur, volume, tipo))
    total = array.array("h")
    for p in partes:
        total.extend(p)
    return total


def mixar(*arrays, volume_total=0.9):
    tamanho = max(len(a) for a in arrays)

    if NUMPY_DISPONIVEL:
        soma = np.zeros(tamanho, dtype=np.float64)
        for a in arrays:
            np_a = np.frombuffer(a.tobytes(), dtype=np.int16).astype(np.float64)
            soma[:len(np_a)] += np_a
        return _array_de_int16(soma * volume_total)

    resultado = array.array("h", [0]) * tamanho
    for i in range(tamanho):
        soma = 0
        for a in arrays:
            if i < len(a):
                soma += a[i]
        soma = int(soma * volume_total)
        resultado[i] = max(-32767, min(32767, soma))
    return resultado


def criar_som(amostras):
    if not SOM_ATIVADO:
        return None
    try:
        return pygame.mixer.Sound(buffer=amostras.tobytes())
    except Exception:
        return None


SONS = {}
MUSICAS = {}  # uma trilha por fase: {1: som, 2: som, ...} + 99 = tema final/creditos
CANAL_MUSICA = None


def tocar(nome):
    if not SOM_ATIVADO:
        return
    som = SONS.get(nome)
    if som is not None:
        som.play()


def parar_musica():
    global CANAL_MUSICA
    if CANAL_MUSICA is not None:
        CANAL_MUSICA.stop()
        CANAL_MUSICA = None


def atualizar_tela_real():
    if not MODO_SCALED:
        tela_final = pygame.transform.scale(CANVAS, (TELA_LARGURA, TELA_ALTURA))
        TELA.blit(tela_final, (0, 0))
    pygame.display.flip()


def tela_carregando(progresso_texto="Carregando..."):
    CANVAS.fill((80, 140, 200))
    texto = FONTE_GRANDE.render(progresso_texto, True, BRANCO)
    CANVAS.blit(texto, (LARGURA // 2 - texto.get_width() // 2, ALTURA // 2 - 30))
    atualizar_tela_real()
    for evento in pygame.event.get():
        pass


# ---------------------------------------------------------
# CONTROLES TOUCH NA TELA
# ---------------------------------------------------------
class ControlesTouch:
    def __init__(self):
        self.btn_esquerda = pygame.Rect(20, 340, 60, 60)
        self.btn_direita = pygame.Rect(90, 340, 60, 60)
        self.btn_pular = pygame.Rect(700, 330, 75, 75)

        self.esquerda = False
        self.direita = False
        self.pular = False
        self.dedos = {}
        self.pulo_solicitado = False

    def consumir_pulo(self):
        if self.pulo_solicitado:
            self.pulo_solicitado = False
            return True
        return False

    def tela_para_canvas(self, pos):
        x, y = pos
        escala_x = LARGURA / TELA_LARGURA
        escala_y = ALTURA / TELA_ALTURA
        return (x * escala_x, y * escala_y)

    def processar_evento(self, evento):
        if evento.type == pygame.FINGERDOWN:
            pos = (evento.x * TELA_LARGURA, evento.y * TELA_ALTURA)
            cpos = self.tela_para_canvas(pos)
            self._pressionar(evento.finger_id, cpos)
        elif evento.type == pygame.FINGERUP:
            self._soltar(evento.finger_id)
        elif evento.type == pygame.FINGERMOTION:
            pos = (evento.x * TELA_LARGURA, evento.y * TELA_ALTURA)
            cpos = self.tela_para_canvas(pos)
            self._soltar(evento.finger_id)
            self._pressionar(evento.finger_id, cpos)
        elif evento.type == pygame.MOUSEBUTTONDOWN:
            cpos = self.tela_para_canvas(evento.pos)
            self._pressionar("mouse", cpos)
        elif evento.type == pygame.MOUSEBUTTONUP:
            self._soltar("mouse")

    def _pressionar(self, fid, cpos):
        if self.btn_esquerda.collidepoint(cpos):
            self.dedos[fid] = "esquerda"
        elif self.btn_direita.collidepoint(cpos):
            self.dedos[fid] = "direita"
        elif self.btn_pular.collidepoint(cpos):
            self.dedos[fid] = "pular"
            self.pulo_solicitado = True
        self._atualizar_estado()

    def _soltar(self, fid):
        if fid in self.dedos:
            del self.dedos[fid]
        self._atualizar_estado()

    def _atualizar_estado(self):
        valores = self.dedos.values()
        self.esquerda = "esquerda" in valores
        self.direita = "direita" in valores
        self.pular = "pular" in valores

    def desenhar(self, canvas):
        overlay = pygame.Surface((LARGURA, ALTURA), pygame.SRCALPHA)

        cor = BRANCO_BOTAO if self.esquerda else CINZA_BOTAO
        pygame.draw.rect(overlay, cor, self.btn_esquerda, border_radius=12)
        cx, cy = self.btn_esquerda.center
        pygame.draw.polygon(overlay, PRETO, [(cx + 8, cy - 12), (cx - 10, cy), (cx + 8, cy + 12)])

        cor = BRANCO_BOTAO if self.direita else CINZA_BOTAO
        pygame.draw.rect(overlay, cor, self.btn_direita, border_radius=12)
        cx, cy = self.btn_direita.center
        pygame.draw.polygon(overlay, PRETO, [(cx - 8, cy - 12), (cx + 10, cy), (cx - 8, cy + 12)])

        cor = BRANCO_BOTAO if self.pular else CINZA_BOTAO
        pygame.draw.ellipse(overlay, cor, self.btn_pular)
        cx, cy = self.btn_pular.center
        pygame.draw.polygon(overlay, PRETO, [(cx, cy - 14), (cx - 12, cy + 10), (cx + 12, cy + 10)])

        canvas.blit(overlay, (0, 0))


CONTROLES = ControlesTouch()


_DISPOSITIVO_TEM_TOQUE_FISICO = False


def obter_posicao_toque(evento):
    """Converte um evento de toque/mouse em coordenadas do canvas (ou None).

    Em celular, o SDL costuma gerar um FINGERDOWN e, separadamente
    (as vezes so no quadro seguinte), um MOUSEBUTTONDOWN sintetico pro
    MESMO toque fisico. Se a gente usasse os dois, cada toque acabava
    sendo processado 2x -- por isso o botao "SIM"/"MENU PRINCIPAL" da
    pausa acabava clicando de novo em "JOGAR" (reiniciando a fase) e o
    botao de musica ligava/desligava em sequencia (parecia so reiniciar
    a musica). Aqui a gente detecta que o aparelho tem tela de toque de
    verdade assim que chega o primeiro FINGERDOWN e, a partir dai,
    ignora os MOUSEBUTTONDOWN (que nesse caso so podem ser ecos
    sinteticos do toque). Em PC sem tela de toque, FINGERDOWN nunca
    acontece, entao o mouse continua funcionando normalmente.
    """
    global _DISPOSITIVO_TEM_TOQUE_FISICO
    if evento.type == pygame.FINGERDOWN:
        _DISPOSITIVO_TEM_TOQUE_FISICO = True
        pos = (evento.x * TELA_LARGURA, evento.y * TELA_ALTURA)
        return CONTROLES.tela_para_canvas(pos)
    elif evento.type == pygame.MOUSEBUTTONDOWN:
        if _DISPOSITIVO_TEM_TOQUE_FISICO:
            return None
        return CONTROLES.tela_para_canvas(evento.pos)
    return None


# ---------------------------------------------------------
# PARTICULAS (moedas, blocos, bolhas, brasas, faiscas...)
# ---------------------------------------------------------
class Particula:
    def __init__(self, x, y, cor, vx=None, vy=None, vida=30, raio=4, gravidade=0.4):
        self.x = x
        self.y = y
        self.vx = vx if vx is not None else random.uniform(-3, 3)
        self.vy = vy if vy is not None else random.uniform(-6, -2)
        self.cor = cor
        self.vida = vida
        self.vida_max = vida
        self.raio = raio
        self.gravidade = gravidade

    def atualizar(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravidade
        self.vida -= 1

    def viva(self):
        return self.vida > 0

    def desenhar(self, canvas, camera_x):
        x = self.x - camera_x
        if -20 < x < LARGURA + 20:
            fator = max(0.0, self.vida / self.vida_max)
            raio = max(1, int(self.raio * fator))
            pygame.draw.rect(canvas, self.cor, (x - raio, self.y - raio, raio * 2, raio * 2))


PARTICULAS = []


def espalhar_particulas(x, y, cor, quantidade=8, gravidade=0.4):
    for _ in range(quantidade):
        PARTICULAS.append(Particula(x, y, cor, vida=random.randint(20, 35), gravidade=gravidade))


def espalhar_bolhas(x, y, quantidade=5):
    for _ in range(quantidade):
        PARTICULAS.append(Particula(
            x + random.uniform(-6, 6), y, (210, 240, 255),
            vx=random.uniform(-0.5, 0.5), vy=random.uniform(-2.5, -1.0),
            vida=random.randint(25, 45), raio=random.randint(2, 4), gravidade=-0.03))


def atualizar_particulas():
    for p in PARTICULAS:
        p.atualizar()
    PARTICULAS[:] = [p for p in PARTICULAS if p.viva()]


def desenhar_particulas(canvas, camera_x):
    for p in PARTICULAS:
        p.desenhar(canvas, camera_x)


# ---------------------------------------------------------
# FRAGMENTOS DE BLOCO (fisica de verdade ao quebrar um bloco)
# ---------------------------------------------------------
class Fragmento:
    def __init__(self, x, y, tamanho, cor, vx, vy):
        self.x = x
        self.y = y
        self.tamanho = tamanho
        self.cor = cor
        self.vx = vx
        self.vy = vy
        self.rotacao = random.uniform(0, 360)
        self.vel_rotacao = random.uniform(-10, 10)
        self.vida = 45
        self.quicou = False

    def _chao_abaixo(self, plataformas):
        melhor = ALTURA + 40
        for plat in plataformas:
            if plat.left - 6 <= self.x <= plat.right + 6 and plat.top >= self.y:
                if plat.top < melhor:
                    melhor = plat.top
        return melhor

    def atualizar(self, plataformas=None):
        self.vx *= 0.97
        self.vy += 0.85
        self.x += self.vx
        self.y += self.vy
        self.rotacao += self.vel_rotacao

        if not self.quicou:
            chao_y = self._chao_abaixo(plataformas) if plataformas else ALTURA - 50
            if self.y > chao_y:
                self.y = chao_y
                self.vy *= -0.35
                self.vx *= 0.5
                self.quicou = True

        self.vida -= 1

    def viva(self):
        return self.vida > 0

    def desenhar(self, canvas, camera_x):
        x = self.x - camera_x
        if -30 < x < LARGURA + 30:
            fator = max(0.0, self.vida / 45)
            tam = max(1, int(self.tamanho * (0.5 + 0.5 * fator)))
            superficie = pygame.Surface((tam, tam), pygame.SRCALPHA)
            superficie.fill(self.cor)
            girado = pygame.transform.rotate(superficie, self.rotacao)
            rect_girado = girado.get_rect(center=(x, self.y))
            canvas.blit(girado, rect_girado)


FRAGMENTOS = []


def espalhar_fragmentos_bloco(rect_bloco, cores):
    cx, cy = rect_bloco.centerx, rect_bloco.centery
    for i in range(6):
        cor = cores[i % len(cores)]
        tam = random.randint(6, max(7, rect_bloco.width // 3))
        origem_x = cx + random.uniform(-rect_bloco.width / 2, rect_bloco.width / 2)
        origem_y = cy + random.uniform(-rect_bloco.height / 2, rect_bloco.height / 2)
        vx = random.uniform(-5.0, 5.0)
        vy = random.uniform(-6.0, -1.5)
        FRAGMENTOS.append(Fragmento(origem_x, origem_y, tam, cor, vx, vy))


def atualizar_fragmentos(plataformas=None):
    for f in FRAGMENTOS:
        f.atualizar(plataformas)
    FRAGMENTOS[:] = [f for f in FRAGMENTOS if f.viva()]


def desenhar_fragmentos(canvas, camera_x):
    for f in FRAGMENTOS:
        f.desenhar(canvas, camera_x)


# ---------------------------------------------------------
# CLASSE DO GATO (JOGADOR)
# ---------------------------------------------------------
class Gato:
    def __init__(self, x, y):
        self.largura = 40
        self.altura = 40
        self.x = x
        self.y = y
        self.vel_y = 0
        self.no_chao = False
        self.direcao = 1
        self.andando = 0
        self.vidas = 3
        self.invencivel = 0
        self.pontos = 0
        self.tem_pulo_duplo = False
        self.pulo_duplo_usado = False
        self._teclado_pulo_antes = False
        self.turbo_timer = 0
        self.quadros_fora_do_chao = 0
        self.buffer_pulo = 0
        self.modo = "normal"  # "normal" ou "agua"

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.largura, self.altura)

    def velocidade_atual(self):
        base = VELOCIDADE_AGUA if self.modo == "agua" else VELOCIDADE
        return base * 1.6 if self.turbo_timer > 0 else base

    def reposicionar(self, x, y):
        self.x = x
        self.y = y
        self.vel_y = 0
        self.no_chao = False
        self.quadros_fora_do_chao = 999
        self.buffer_pulo = 0

    def atualizar(self, teclas, plataformas_solidas, controles, deslocamentos=None):
        na_agua = self.modo == "agua"
        gravidade = GRAVIDADE_AGUA if na_agua else GRAVIDADE
        queda_max = QUEDA_MAX_AGUA if na_agua else 20

        mover = 0
        ir_esquerda = teclas[pygame.K_LEFT] or controles.esquerda
        ir_direita = teclas[pygame.K_RIGHT] or controles.direita

        vel = self.velocidade_atual()
        if ir_esquerda:
            mover = -vel
            self.direcao = -1
            self.andando += 1
        elif ir_direita:
            mover = vel
            self.direcao = 1
            self.andando += 1
        else:
            self.andando = 0

        self.x += mover
        self.x = max(0, self.x)

        pular_teclado = teclas[pygame.K_SPACE] or teclas[pygame.K_UP]
        pulo_borda_teclado = pular_teclado and not self._teclado_pulo_antes
        self._teclado_pulo_antes = pular_teclado
        pulo_solicitado_agora = pulo_borda_teclado or controles.consumir_pulo()

        if na_agua:
            # nadar: cada toque da um impulso pra cima, sem limite de
            # "pulo duplo" -- e assim que se nada num jogo 2D
            if pulo_solicitado_agora:
                self.vel_y = IMPULSO_NADO
                tocar("pulo")
                espalhar_bolhas(self.x + self.largura // 2, self.y + self.altura, 4)
        else:
            if pulo_solicitado_agora:
                self.buffer_pulo = 6
            elif self.buffer_pulo > 0:
                self.buffer_pulo -= 1

            pode_pular_normal = self.no_chao or self.quadros_fora_do_chao <= 6

            if self.buffer_pulo > 0 and pode_pular_normal:
                self.vel_y = PULO_FORCA
                self.no_chao = False
                self.quadros_fora_do_chao = 999
                self.pulo_duplo_usado = False
                self.buffer_pulo = 0
                tocar("pulo")
            elif self.buffer_pulo > 0 and self.tem_pulo_duplo and not self.pulo_duplo_usado and not self.no_chao:
                self.vel_y = PULO_FORCA * 0.85
                self.pulo_duplo_usado = True
                self.buffer_pulo = 0
                tocar("pulo_duplo")
                espalhar_particulas(self.x + self.largura // 2, self.y + self.altura, (120, 220, 255), 10)

        self.vel_y += gravidade
        if self.vel_y > queda_max:
            self.vel_y = queda_max
        if na_agua and self.vel_y < -queda_max:
            self.vel_y = -queda_max
        self.y += self.vel_y

        estava_no_chao = self.no_chao
        self.no_chao = False
        gato_rect = self.rect()
        plataforma_embaixo = None
        if self.vel_y >= 0:
            for plat in plataformas_solidas:
                if gato_rect.colliderect(plat):
                    if gato_rect.bottom - self.vel_y <= plat.top + 10:
                        self.y = plat.top - self.altura
                        self.vel_y = 0
                        self.no_chao = True
                        self.pulo_duplo_usado = False
                        gato_rect = self.rect()
                        plataforma_embaixo = plat

        if self.no_chao:
            self.quadros_fora_do_chao = 0
        elif estava_no_chao:
            self.quadros_fora_do_chao = 0
        else:
            self.quadros_fora_do_chao += 1

        if self.vel_y < 0:
            gato_rect = self.rect()
            for plat in plataformas_solidas:
                if gato_rect.colliderect(plat) and gato_rect.top - self.vel_y >= plat.bottom - 10:
                    self.y = plat.bottom
                    self.vel_y = 0
                    gato_rect = self.rect()

        gato_rect = self.rect()
        for plat in plataformas_solidas:
            if not gato_rect.colliderect(plat):
                continue
            sobreposicao_topo = gato_rect.bottom - plat.top
            sobreposicao_base = plat.bottom - gato_rect.top
            if sobreposicao_topo > 8 and sobreposicao_base > 8:
                centro_gato = gato_rect.centerx
                if centro_gato < plat.centerx:
                    self.x = plat.left - self.largura
                else:
                    self.x = plat.right
                gato_rect = self.rect()

        if plataforma_embaixo is not None and deslocamentos:
            self.x += deslocamentos.get(id(plataforma_embaixo), 0)

        if self.invencivel > 0:
            self.invencivel -= 1
        if self.turbo_timer > 0:
            self.turbo_timer -= 1

        if self.y > ALTURA + 200:
            self.perder_vida()

        if na_agua and random.random() < 0.06:
            espalhar_bolhas(self.x + self.largura // 2, self.y + self.altura // 2, 1)

    def perder_vida(self, ponto_reinicio=(60, 100)):
        self.vidas -= 1
        self.pontos = max(0, self.pontos - 50)
        self.x, self.y = ponto_reinicio
        self.vel_y = 0
        self.invencivel = 90
        self.quadros_fora_do_chao = 999
        self.buffer_pulo = 0
        tocar("perder_vida")

    def desenhar(self, canvas, camera_x):
        cx = self.x - camera_x
        cy = self.y

        sombra = pygame.Surface((self.largura, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(sombra, (0, 0, 0, 70), sombra.get_rect())
        canvas.blit(sombra, (cx, cy + self.altura - 4))

        if self.invencivel > 0 and self.invencivel % 10 < 5:
            return

        pulinho = 3 if (self.andando // 6) % 2 == 0 and self.no_chao and self.andando > 0 else 0

        if self.direcao == 1:
            pygame.draw.arc(canvas, LARANJA_GATO_ESCURO, (cx - 20, cy + pulinho, 28, 36), -0.6, 2.4, 5)
        else:
            pygame.draw.arc(canvas, LARANJA_GATO_ESCURO, (cx + self.largura - 8, cy + pulinho, 28, 36), 0.7, 3.7, 5)

        pata_y = cy + self.altura - 5 + pulinho
        for dx in (5, 27):
            pygame.draw.ellipse(canvas, LARANJA_GATO_ESCURO, (cx + dx, pata_y, 9, 7))

        corpo = pygame.Rect(cx, cy + pulinho + 4, self.largura, self.altura - pulinho - 6)
        pygame.draw.ellipse(canvas, LARANJA_GATO, corpo)
        pygame.draw.ellipse(canvas, LARANJA_GATO_ESCURO, corpo, 2)

        for lx in (8, 18, 28):
            pygame.draw.arc(canvas, LARANJA_GATO_ESCURO,
                             (cx + lx - 5, cy + pulinho + 2, 12, 14), 3.6, 5.8, 2)

        raio_cabeca = 15
        cabeca_cx = cx + 26 if self.direcao == 1 else cx + 14
        cabeca_cy = cy + pulinho + 13
        pygame.draw.circle(canvas, LARANJA_GATO, (cabeca_cx, cabeca_cy), raio_cabeca)
        pygame.draw.circle(canvas, LARANJA_GATO_ESCURO, (cabeca_cx, cabeca_cy), raio_cabeca, 2)

        base_orelha_y = cabeca_cy - raio_cabeca + 4
        orelha_esq = [(cabeca_cx - 13, base_orelha_y + 4), (cabeca_cx - 8, base_orelha_y - 13), (cabeca_cx - 1, base_orelha_y + 2)]
        orelha_dir = [(cabeca_cx + 1, base_orelha_y + 2), (cabeca_cx + 8, base_orelha_y - 13), (cabeca_cx + 13, base_orelha_y + 4)]
        pygame.draw.polygon(canvas, LARANJA_GATO, orelha_esq)
        pygame.draw.polygon(canvas, LARANJA_GATO, orelha_dir)
        pygame.draw.polygon(canvas, ROSA, [(cabeca_cx - 9, base_orelha_y), (cabeca_cx - 7, base_orelha_y - 7), (cabeca_cx - 3, base_orelha_y - 1)])
        pygame.draw.polygon(canvas, ROSA, [(cabeca_cx + 3, base_orelha_y - 1), (cabeca_cx + 7, base_orelha_y - 7), (cabeca_cx + 9, base_orelha_y)])

        olho_x = cabeca_cx + 6 if self.direcao == 1 else cabeca_cx - 6
        olho_x2 = cabeca_cx - 6 if self.direcao == 1 else cabeca_cx + 6
        for ox in (olho_x, olho_x2):
            pygame.draw.ellipse(canvas, (150, 230, 100), (ox - 4, cabeca_cy - 4, 8, 8))
            pygame.draw.ellipse(canvas, PRETO, (ox - 1, cabeca_cy - 3, 2, 6))

        focinho_x = cabeca_cx + 12 if self.direcao == 1 else cabeca_cx - 12
        pygame.draw.polygon(canvas, ROSA, [(focinho_x - 3, cabeca_cy + 4), (focinho_x + 3, cabeca_cy + 4), (focinho_x, cabeca_cy + 8)])
        pygame.draw.arc(canvas, PRETO, (focinho_x - 6, cabeca_cy + 6, 7, 6), 3.3, 6.3, 1)
        pygame.draw.arc(canvas, PRETO, (focinho_x - 1, cabeca_cy + 6, 7, 6), 2.9, 5.9, 1)

        sinal = 1 if self.direcao == 1 else -1
        for dy in (-3, 0, 3):
            pygame.draw.line(canvas, BRANCO,
                              (focinho_x + 2 * sinal, cabeca_cy + 5 + dy),
                              (focinho_x + 14 * sinal, cabeca_cy + 3 + dy), 1)


# ---------------------------------------------------------
# PLATAFORMAS MOVEIS (reutilizada em todas as fases, cor customizavel)
# ---------------------------------------------------------
class PlataformaMovel:
    def __init__(self, x, y, largura, altura, min_x, max_x, vel,
                 cor=(140, 140, 160), cor_escura=(95, 95, 115), min_y=None, max_y=None):
        self.x = x
        self.y = y
        self.width = largura
        self.height = altura
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y
        self.vel = vel
        self.deslocamento_x = 0
        self.cor = cor
        self.cor_escura = cor_escura
        self.vertical = min_y is not None and max_y is not None

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

    def atualizar(self):
        antes = self.x
        if self.vertical:
            self.y += self.vel
            if self.y < self.min_y or self.y > self.max_y:
                self.vel *= -1
                self.y = max(self.min_y, min(self.y, self.max_y))
        else:
            self.x += self.vel
            if self.x < self.min_x or self.x > self.max_x:
                self.vel *= -1
                self.x = max(self.min_x, min(self.x, self.max_x))
        self.deslocamento_x = self.x - antes

    def desenhar(self, canvas, camera_x):
        x = self.x - camera_x
        if x + self.width < 0 or x > LARGURA:
            return
        r = pygame.Rect(x, self.y, self.width, self.height)
        pygame.draw.rect(canvas, self.cor, r, border_radius=4)
        pygame.draw.rect(canvas, self.cor_escura, r, 3, border_radius=4)
        for tx in range(0, self.width, 16):
            pygame.draw.line(canvas, self.cor_escura, (x + tx, self.y), (x + tx, self.y + self.height), 1)


# ---------------------------------------------------------
# PERIGOS (espinhos / ourico do mar / raios / lava - visual muda
# conforme o "estilo", mas a colisao e sempre a mesma: perde vida)
# ---------------------------------------------------------
def desenhar_perigos(canvas, camera_x, perigos, estilo="espinho"):
    for e in perigos:
        x = e.x - camera_x
        if x + e.width < 0 or x > LARGURA:
            continue

        if estilo == "espinho":
            num_picos = max(1, e.width // 14)
            largura_pico = e.width / num_picos
            for i in range(num_picos):
                px = x + i * largura_pico
                pygame.draw.polygon(canvas, (200, 200, 210), [
                    (px, e.bottom), (px + largura_pico / 2, e.top), (px + largura_pico, e.bottom)])
                pygame.draw.polygon(canvas, (130, 130, 145), [
                    (px, e.bottom), (px + largura_pico / 2, e.top), (px + largura_pico, e.bottom)], 2)

        elif estilo == "ourico":
            cx_, cy_ = x + e.width / 2, e.centery
            pygame.draw.circle(canvas, (40, 30, 60), (int(cx_), int(cy_)), e.height // 2)
            for ang in range(0, 360, 30):
                rad = math.radians(ang)
                ponta = (cx_ + math.cos(rad) * (e.width / 2 + 4), cy_ + math.sin(rad) * (e.height / 2 + 4))
                pygame.draw.line(canvas, (90, 60, 140), (cx_, cy_), ponta, 2)

        elif estilo == "raio":
            pygame.draw.polygon(canvas, (255, 235, 90), [
                (x + e.width * 0.6, e.top), (x, e.top + e.height * 0.55),
                (x + e.width * 0.45, e.top + e.height * 0.55),
                (x + e.width * 0.1, e.bottom),
                (x + e.width, e.top + e.height * 0.35),
                (x + e.width * 0.55, e.top + e.height * 0.35)])
            pygame.draw.polygon(canvas, (255, 255, 200), [
                (x + e.width * 0.6, e.top), (x, e.top + e.height * 0.55),
                (x + e.width * 0.45, e.top + e.height * 0.55),
                (x + e.width * 0.1, e.bottom),
                (x + e.width, e.top + e.height * 0.35),
                (x + e.width * 0.55, e.top + e.height * 0.35)], 1)

        elif estilo == "lava":
            pulso = int(6 * abs(math.sin(pygame.time.get_ticks() * 0.005 + x)))
            pygame.draw.rect(canvas, (120, 20, 10), (x, e.top, e.width, e.height))
            pygame.draw.rect(canvas, (255, 110, 20), (x, e.top - pulso, e.width, 6 + pulso))
            for bx in range(0, e.width, 10):
                if random.random() < 0.15:
                    espalhar_particulas(x + bx, e.top, (255, 150, 40), 1, gravidade=-0.15)


def checar_perigos(perigos, gato, ponto_reinicio):
    if gato.invencivel > 0:
        return
    gato_rect = gato.rect()
    for e in perigos:
        if gato_rect.colliderect(e):
            gato.perder_vida(ponto_reinicio)
            espalhar_particulas(gato_rect.centerx, gato_rect.centery, VERMELHO, 8)
            return


# ---------------------------------------------------------
# BLOCOS QUEBRAVEIS (cores customizaveis por fase)
# ---------------------------------------------------------
DURACAO_SOLAVANCO = 5


def criar_bloco(x, y, com_moeda, largura=36, altura=30):
    return {"rect": pygame.Rect(x, y, largura, altura), "estado": "intacto",
            "timer": 0, "com_moeda": com_moeda}


def desenhar_blocos(canvas, camera_x, blocos, cor, cor_escura):
    for bloco in blocos:
        estado = bloco["estado"]
        if estado == "sumiu":
            continue
        r = bloco["rect"]
        x = r.x - camera_x
        if x + r.width < 0 or x > LARGURA:
            continue

        offset_y = 0
        if estado == "batendo":
            progresso = bloco["timer"] / DURACAO_SOLAVANCO
            offset_y = -7 * math.sin(progresso * math.pi)

        rect_tela = pygame.Rect(x, r.y + offset_y, r.width, r.height)
        pygame.draw.rect(canvas, cor, rect_tela)
        pygame.draw.rect(canvas, cor_escura, rect_tela, 3)
        pygame.draw.line(canvas, cor_escura, (rect_tela.x, rect_tela.y + rect_tela.height // 2),
                          (rect_tela.x + rect_tela.width, rect_tela.y + rect_tela.height // 2), 2)


def _empurrar_para_fora_do_bloco(gato, gato_rect, r):
    """Colisao lateral: se o gato esta mais 'do lado' do bloco do que em
    cima/embaixo dele, empurra pra fora -- e o que faltava para o bloco
    ficar solido igual ele e desenhado, em vez de atravessavel pelos lados."""
    sobreposicao_topo = gato_rect.bottom - r.top
    sobreposicao_base = r.bottom - gato_rect.top
    if sobreposicao_topo > 8 and sobreposicao_base > 8:
        if gato_rect.centerx < r.centerx:
            gato.x = r.left - gato.largura
        else:
            gato.x = r.right
        return gato.rect()
    return gato_rect


def atualizar_blocos(blocos, gato, moedas, cores_fragmento):
    gato_rect = gato.rect()
    for bloco in blocos:
        if bloco["estado"] == "intacto":
            r = bloco["rect"]
            if gato_rect.colliderect(r):
                if gato.vel_y < 0 and gato_rect.top - gato.vel_y >= r.bottom - 10:
                    bloco["estado"] = "batendo"
                    bloco["timer"] = DURACAO_SOLAVANCO
                    gato.vel_y = 2
                    gato_rect = gato.rect()
                elif gato.vel_y >= 0 and gato_rect.bottom - gato.vel_y <= r.top + 10:
                    gato.y = r.top - gato.altura
                    gato.vel_y = 0
                    gato.no_chao = True
                    gato.pulo_duplo_usado = False
                    gato.quadros_fora_do_chao = 0
                    gato_rect = gato.rect()
                else:
                    gato_rect = _empurrar_para_fora_do_bloco(gato, gato_rect, r)
        elif bloco["estado"] == "batendo":
            r = bloco["rect"]
            if gato_rect.colliderect(r):
                if gato.vel_y >= 0 and gato_rect.bottom - gato.vel_y <= r.top + 10:
                    gato.y = r.top - gato.altura
                    gato.vel_y = 0
                    gato.no_chao = True
                    gato.pulo_duplo_usado = False
                    gato.quadros_fora_do_chao = 0
                    gato_rect = gato.rect()
                else:
                    gato_rect = _empurrar_para_fora_do_bloco(gato, gato_rect, r)

            bloco["timer"] -= 1
            if bloco["timer"] <= 0:
                bloco["estado"] = "sumiu"
                tocar("quebrar")
                espalhar_fragmentos_bloco(r, cores_fragmento)
                espalhar_particulas(r.centerx, r.bottom - 4, (190, 190, 195), 6)
                if bloco["com_moeda"]:
                    moedas.append(pygame.Rect(r.x + 8, r.y - 30, 20, 20))


# ---------------------------------------------------------
# MOEDAS
# ---------------------------------------------------------
def desenhar_moedas(canvas, camera_x, moedas, quadro):
    largura_moeda = max(4, int(20 * abs(math.cos(quadro * 0.08))))
    for m in moedas:
        x = m.x - camera_x
        if x + m.width < 0 or x > LARGURA:
            continue
        centro_x = x + m.width // 2
        pygame.draw.ellipse(canvas, AMARELO_MOEDA,
                             (centro_x - largura_moeda // 2, m.y, largura_moeda, m.height))
        pygame.draw.ellipse(canvas, AMARELO_MOEDA_ESCURO,
                             (centro_x - largura_moeda // 2, m.y, largura_moeda, m.height), 2)


def atualizar_moedas(moedas, gato):
    gato_rect = gato.rect()
    coletadas = [m for m in moedas if gato_rect.colliderect(m)]
    for m in coletadas:
        espalhar_particulas(m.centerx, m.centery, AMARELO_MOEDA, 8)
        gato.pontos += 10
        tocar("moeda")
    moedas[:] = [m for m in moedas if m not in coletadas]


# ---------------------------------------------------------
# INIMIGOS (tipos: chao, voador, peixe, tubarao, eletrico, lava)
# ---------------------------------------------------------
def criar_inimigo_chao(x, y, min_x, max_x, vel):
    return {"rect": pygame.Rect(x, y, 30, 30), "min_x": min_x, "max_x": max_x,
            "vel": vel, "vivo": True, "tipo": "chao"}


def criar_inimigo_voador(x, y, min_x, max_x, vel, base_y, fase=0.0):
    return {"rect": pygame.Rect(x, y, 30, 30), "min_x": min_x, "max_x": max_x,
            "vel": vel, "vivo": True, "tipo": "voador", "base_y": base_y, "fase": fase}


def criar_peixe(x, y, min_x, max_x, vel, base_y, fase=0.0):
    return {"rect": pygame.Rect(x, y, 28, 20), "min_x": min_x, "max_x": max_x,
            "vel": vel, "vivo": True, "tipo": "peixe", "base_y": base_y, "fase": fase}


def criar_tubarao(x, y, min_x, max_x, vel):
    return {"rect": pygame.Rect(x, y, 52, 30), "min_x": min_x, "max_x": max_x,
            "vel": vel, "vel_base": vel, "vivo": True, "tipo": "tubarao"}


def criar_eletrico(x, y, min_x, max_x, vel, base_y, fase=0.0):
    return {"rect": pygame.Rect(x, y, 26, 26), "min_x": min_x, "max_x": max_x,
            "vel": vel, "vivo": True, "tipo": "eletrico", "base_y": base_y, "fase": fase}


def criar_lava_inimigo(x, y, min_x, max_x, vel):
    return {"rect": pygame.Rect(x, y, 34, 26), "min_x": min_x, "max_x": max_x,
            "vel": vel, "vivo": True, "tipo": "lava", "pulso": 0.0}


def desenhar_inimigos(canvas, camera_x, inimigos):
    for inimigo in inimigos:
        if not inimigo["vivo"]:
            continue
        r = inimigo["rect"]
        x = r.x - camera_x
        if x + r.width < 0 or x > LARGURA:
            continue
        tipo = inimigo["tipo"]

        if tipo == "voador":
            bater = 6 * math.sin(pygame.time.get_ticks() * 0.02)
            pygame.draw.ellipse(canvas, (240, 240, 255), (x - 8, r.y + 8 + bater, 14, 8))
            pygame.draw.ellipse(canvas, (240, 240, 255), (x + r.width - 6, r.y + 8 - bater, 14, 8))
            pygame.draw.ellipse(canvas, ROXO, (x, r.y, r.width, r.height))
            pygame.draw.ellipse(canvas, (100, 40, 150), (x, r.y, r.width, r.height), 2)
            pygame.draw.circle(canvas, BRANCO, (int(x + r.width * 0.3), r.y + 10), 4)
            pygame.draw.circle(canvas, BRANCO, (int(x + r.width * 0.7), r.y + 10), 4)
            pygame.draw.circle(canvas, PRETO, (int(x + r.width * 0.3), r.y + 10), 2)
            pygame.draw.circle(canvas, PRETO, (int(x + r.width * 0.7), r.y + 10), 2)

        elif tipo == "chao":
            pygame.draw.polygon(canvas, (25, 25, 25), [(x + 5, r.y + 6), (x - 2, r.y - 9), (x + 10, r.y + 3)])
            pygame.draw.polygon(canvas, (25, 25, 25), [(x + r.width - 5, r.y + 6), (x + r.width + 2, r.y - 9), (x + r.width - 10, r.y + 3)])
            pygame.draw.ellipse(canvas, VERMELHO, (x, r.y, r.width, r.height))
            pygame.draw.ellipse(canvas, (110, 15, 15), (x, r.y, r.width, r.height), 2)
            pygame.draw.circle(canvas, BRANCO, (int(x + r.width * 0.3), r.y + 10), 4)
            pygame.draw.circle(canvas, BRANCO, (int(x + r.width * 0.7), r.y + 10), 4)
            pygame.draw.circle(canvas, PRETO, (int(x + r.width * 0.3), r.y + 10), 2)
            pygame.draw.circle(canvas, PRETO, (int(x + r.width * 0.7), r.y + 10), 2)

        elif tipo == "peixe":
            sinal = 1 if inimigo["vel"] >= 0 else -1
            corpo = pygame.Rect(x, r.y, r.width, r.height)
            pygame.draw.ellipse(canvas, (255, 140, 60), corpo)
            pygame.draw.ellipse(canvas, (200, 90, 30), corpo, 2)
            cauda_x = x if sinal > 0 else x + r.width
            ponta = cauda_x - 10 * sinal
            pygame.draw.polygon(canvas, (255, 140, 60), [
                (cauda_x, r.y + 2), (ponta, r.centery), (cauda_x, r.bottom - 2)])
            olho_x = x + r.width * 0.75 if sinal > 0 else x + r.width * 0.25
            pygame.draw.circle(canvas, BRANCO, (int(olho_x), r.y + 8), 3)
            pygame.draw.circle(canvas, PRETO, (int(olho_x), r.y + 8), 1)

        elif tipo == "tubarao":
            sinal = 1 if inimigo["vel"] >= 0 else -1
            corpo = pygame.Rect(x, r.y, r.width, r.height)
            pygame.draw.ellipse(canvas, (120, 130, 140), corpo)
            pygame.draw.ellipse(canvas, (70, 80, 90), corpo, 2)
            barbatana_x = x + r.width * 0.4
            pygame.draw.polygon(canvas, (100, 110, 120), [
                (barbatana_x, r.y), (barbatana_x + 10, r.y - 14), (barbatana_x + 18, r.y)])
            cauda_x = x if sinal > 0 else x + r.width
            ponta = cauda_x - 16 * sinal
            pygame.draw.polygon(canvas, (120, 130, 140), [
                (cauda_x, r.y), (ponta, r.centery), (cauda_x, r.bottom)])
            focinho_x = x + r.width if sinal > 0 else x
            olho_x = focinho_x - 12 * sinal
            pygame.draw.circle(canvas, (240, 60, 60), (int(olho_x), r.y + 9), 3)
            for i in range(3):
                dente_x = focinho_x - (4 + i * 4) * sinal
                pygame.draw.polygon(canvas, BRANCO, [
                    (dente_x, r.bottom - 6), (dente_x + 3 * sinal, r.bottom - 6), (dente_x + 1.5 * sinal, r.bottom - 2)])

        elif tipo == "eletrico":
            pulso = 3 * math.sin(pygame.time.get_ticks() * 0.02)
            raio = int(r.width / 2 + pulso)
            centro = (int(x + r.width / 2), int(r.y + r.height / 2))
            halo = pygame.Surface((raio * 3, raio * 3), pygame.SRCALPHA)
            pygame.draw.circle(halo, (255, 255, 120, 90), (raio * 3 // 2, raio * 3 // 2), raio + 6)
            canvas.blit(halo, (centro[0] - raio * 3 // 2, centro[1] - raio * 3 // 2), special_flags=pygame.BLEND_RGBA_ADD)
            pygame.draw.circle(canvas, (255, 230, 60), centro, raio)
            pygame.draw.circle(canvas, (255, 255, 255), centro, raio, 2)
            for ang in (0, 90, 180, 270):
                rad = math.radians(ang + pygame.time.get_ticks() * 0.1)
                ponta = (centro[0] + math.cos(rad) * (raio + 8), centro[1] + math.sin(rad) * (raio + 8))
                pygame.draw.line(canvas, (255, 255, 180), centro, ponta, 2)
            pygame.draw.circle(canvas, PRETO, (centro[0] - 4, centro[1] - 2), 2)
            pygame.draw.circle(canvas, PRETO, (centro[0] + 4, centro[1] - 2), 2)

        elif tipo == "lava":
            pulso = 3 * math.sin(inimigo["pulso"])
            corpo = pygame.Rect(x - pulso / 2, r.y - pulso / 2, r.width + pulso, r.height + pulso)
            pygame.draw.ellipse(canvas, (255, 100, 20), corpo)
            pygame.draw.ellipse(canvas, (180, 40, 10), corpo, 3)
            for bx in range(3):
                bxp = x + 6 + bx * 10
                pygame.draw.circle(canvas, (255, 200, 60), (int(bxp), int(r.centery)), 3)
            pygame.draw.circle(canvas, (30, 10, 5), (int(x + r.width * 0.35), r.y + 8), 3)
            pygame.draw.circle(canvas, (30, 10, 5), (int(x + r.width * 0.65), r.y + 8), 3)


def atualizar_inimigos(inimigos, gato, ponto_reinicio):
    gato_rect = gato.rect()
    for inimigo in inimigos:
        if not inimigo["vivo"]:
            continue
        r = inimigo["rect"]
        tipo = inimigo["tipo"]

        if tipo in ("chao", "peixe"):
            r.x += inimigo["vel"]
            if r.x < inimigo["min_x"] or r.x > inimigo["max_x"]:
                inimigo["vel"] *= -1
                r.x = max(inimigo["min_x"], min(r.x, inimigo["max_x"]))
            if tipo == "peixe":
                inimigo["fase"] += 0.06
                r.y = int(inimigo["base_y"] + 20 * math.sin(inimigo["fase"]))

        elif tipo in ("voador", "eletrico"):
            r.x += inimigo["vel"]
            if r.x < inimigo["min_x"] or r.x > inimigo["max_x"]:
                inimigo["vel"] *= -1
                r.x = max(inimigo["min_x"], min(r.x, inimigo["max_x"]))
            inimigo["fase"] += 0.05 if tipo == "voador" else 0.09
            r.y = int(inimigo["base_y"] + 25 * math.sin(inimigo["fase"]))

        elif tipo == "tubarao":
            # nada de um lado pro outro, mas acelera se o gato estiver perto
            distancia = abs(gato_rect.centerx - r.centerx)
            alvo_vel = inimigo["vel_base"] * (2.0 if distancia < 200 else 1.0)
            direcao = 1 if inimigo["vel"] >= 0 else -1
            inimigo["vel"] = alvo_vel * direcao
            r.x += inimigo["vel"]
            if r.x < inimigo["min_x"] or r.x > inimigo["max_x"]:
                inimigo["vel"] *= -1
                r.x = max(inimigo["min_x"], min(r.x, inimigo["max_x"]))

        elif tipo == "lava":
            inimigo["pulso"] += 0.15
            r.x += inimigo["vel"]
            if r.x < inimigo["min_x"] or r.x > inimigo["max_x"]:
                inimigo["vel"] *= -1
                r.x = max(inimigo["min_x"], min(r.x, inimigo["max_x"]))
            if random.random() < 0.1:
                espalhar_particulas(r.centerx, r.top, (255, 140, 40), 1, gravidade=0.2)

        if gato_rect.colliderect(r):
            if tipo == "lava":
                # lava sempre machuca, nao da pra pisar em cima
                if gato.invencivel == 0:
                    gato.perder_vida(ponto_reinicio)
                    espalhar_particulas(r.centerx, r.centery, (255, 120, 30), 10)
                continue

            pode_pisar = gato.vel_y > 0 and gato_rect.bottom - gato.vel_y <= r.top + 12
            if tipo == "peixe" and gato.modo == "agua":
                # na agua, encostar em qualquer direcao derrota o peixinho
                pode_pisar = True

            if pode_pisar:
                inimigo["vivo"] = False
                if gato.modo != "agua":
                    gato.vel_y = PULO_FORCA * 0.6
                else:
                    gato.vel_y = IMPULSO_NADO * 0.6
                gato.pontos += 50
                tocar("stomp")
                cor_efeito = ROXO if tipo in ("voador", "eletrico") else (255, 210, 120) if tipo == "peixe" else (150, 150, 160)
                espalhar_particulas(r.centerx, r.centery, cor_efeito, 10)
            elif gato.invencivel == 0:
                gato.perder_vida(ponto_reinicio)


# ---------------------------------------------------------
# POWER-UPS
# ---------------------------------------------------------
def desenhar_powerups(canvas, camera_x, powerups, quadro):
    for p in powerups:
        if p["coletado"]:
            continue
        r = p["rect"]
        x = r.x - camera_x
        if x + r.width < 0 or x > LARGURA:
            continue
        centro = (int(x + r.width // 2), int(r.y + r.height // 2))
        pulso = 3 * math.sin(quadro * 0.12)
        raio = int(15 + pulso)

        cor_halo = (100, 220, 255, 70) if p["tipo"] == "pulo_duplo" else (100, 255, 170, 70)
        cor_bola = (60, 170, 255) if p["tipo"] == "pulo_duplo" else (40, 200, 130)

        halo = pygame.Surface((raio * 3, raio * 3), pygame.SRCALPHA)
        pygame.draw.circle(halo, cor_halo, (raio * 3 // 2, raio * 3 // 2), raio + 6)
        canvas.blit(halo, (centro[0] - raio * 3 // 2, centro[1] - raio * 3 // 2), special_flags=pygame.BLEND_RGBA_ADD)

        pygame.draw.circle(canvas, cor_bola, centro, raio)
        pygame.draw.circle(canvas, BRANCO, centro, raio, 2)

        cx_i, cy_i = centro
        if p["tipo"] == "pulo_duplo":
            pygame.draw.polygon(canvas, BRANCO, [(cx_i, cy_i - 9), (cx_i - 6, cy_i - 2), (cx_i + 6, cy_i - 2)])
            pygame.draw.polygon(canvas, BRANCO, [(cx_i, cy_i - 1), (cx_i - 6, cy_i + 6), (cx_i + 6, cy_i + 6)])
        else:
            pygame.draw.polygon(canvas, BRANCO, [
                (cx_i + 4, cy_i - 10), (cx_i - 6, cy_i + 2), (cx_i, cy_i + 2),
                (cx_i - 4, cy_i + 10), (cx_i + 6, cy_i - 2), (cx_i, cy_i - 2)])


def atualizar_powerups(powerups, gato):
    gato_rect = gato.rect()
    for p in powerups:
        if not p["coletado"] and gato_rect.colliderect(p["rect"]):
            p["coletado"] = True
            if p["tipo"] == "pulo_duplo":
                gato.tem_pulo_duplo = True
            elif p["tipo"] == "turbo":
                gato.turbo_timer = 60 * 8
            espalhar_particulas(p["rect"].centerx, p["rect"].centery, (100, 200, 255), 14)
            tocar("powerup")


def desenhar_bandeira(canvas, camera_x, bandeira):
    x = bandeira.x - camera_x
    if x + bandeira.width < 0 or x > LARGURA:
        return
    pygame.draw.rect(canvas, (200, 200, 200), (x, bandeira.y, bandeira.width, bandeira.height))
    pygame.draw.polygon(canvas, VERMELHO, [(x + bandeira.width, bandeira.y + 5),
                                            (x + bandeira.width + 35, bandeira.y + 20),
                                            (x + bandeira.width, bandeira.y + 35)])


# ===========================================================
# FUNDOS (um gradiente + elementos de parallax proprios por fase)
# ===========================================================
def criar_gradiente(cor_topo, cor_base):
    superficie = pygame.Surface((LARGURA, ALTURA))
    for i in range(ALTURA):
        cor = [cor_topo[c] + (cor_base[c] - cor_topo[c]) * i // ALTURA for c in range(3)]
        pygame.draw.line(superficie, cor, (0, i), (LARGURA, i))
    return superficie


GRADIENTE_FASE1 = criar_gradiente((135, 206, 250), (255, 223, 186))
GRADIENTE_FASE2 = criar_gradiente((10, 60, 120), (60, 170, 200))
GRADIENTE_FASE3 = criar_gradiente((120, 190, 255), (235, 245, 255))
GRADIENTE_FASE4 = criar_gradiente((40, 12, 15), (150, 55, 20))
GRADIENTE_FASE5 = criar_gradiente((35, 8, 20), (110, 20, 25))


def _sol_ou_lua(superficie, pos, cor, raios):
    for raio, alpha in raios:
        halo = pygame.Surface((raio * 2, raio * 2), pygame.SRCALPHA)
        pygame.draw.circle(halo, (*cor, alpha), (raio, raio), raio)
        superficie.blit(halo, (pos[0] - raio, pos[1] - raio), special_flags=pygame.BLEND_RGBA_ADD)
    pygame.draw.circle(superficie, cor, pos, raios[-1][0] // 2)


_sol_ou_lua(GRADIENTE_FASE1, (650, 70), (255, 236, 150), [(70, 40), (55, 60), (40, 90)])
_sol_ou_lua(GRADIENTE_FASE4, (200, 60), (255, 180, 90), [(60, 50), (45, 70)])
_sol_ou_lua(GRADIENTE_FASE5, (400, 60), (255, 90, 70), [(90, 50), (60, 80)])


def desenhar_fundo(canvas, camera_x, indice_fase, quadro):
    if indice_fase == 1:
        canvas.blit(GRADIENTE_FASE1, (0, 0))
        for nx, ny in [(-100, 80), (250, 40), (600, 90), (950, 50), (1300, 80), (1650, 40), (2000, 90),
                        (2350, 60), (2700, 90), (3050, 50)]:
            x = nx - camera_x * 0.15
            if -200 < x < LARGURA + 200:
                pygame.draw.polygon(canvas, ROXO_CLARO, [(x, 400), (x + 100, 300), (x + 200, 400)])
        for nx, ny in [(100, 60), (400, 100), (700, 50), (1000, 80), (1400, 60), (1800, 100), (2200, 60),
                        (2600, 90), (3000, 50)]:
            x = nx - camera_x * 0.3
            if -100 < x < LARGURA + 100:
                pygame.draw.ellipse(canvas, BRANCO, (x, ny, 80, 35))
                pygame.draw.ellipse(canvas, BRANCO, (x + 25, ny - 15, 60, 35))

    elif indice_fase == 2:
        canvas.blit(GRADIENTE_FASE2, (0, 0))
        # raios de luz atravessando a agua
        for i, nx in enumerate([150, 500, 900, 1300, 1700, 2100, 2500, 2900]):
            x = nx - camera_x * 0.2
            if -80 < x < LARGURA + 80:
                raio = pygame.Surface((60, ALTURA), pygame.SRCALPHA)
                pygame.draw.polygon(raio, (255, 255, 255, 18), [(30, 0), (60, ALTURA), (0, ALTURA)])
                canvas.blit(raio, (x - 30, 0))
        # algas ao fundo
        for nx, altura_alga in [(80, 120), (400, 150), (760, 100), (1120, 170), (1480, 130),
                                  (1840, 160), (2200, 110), (2560, 150), (2920, 130)]:
            x = nx - camera_x * 0.35
            if -40 < x < LARGURA + 40:
                onda = 8 * math.sin(quadro * 0.03 + nx)
                pygame.draw.polygon(canvas, (10, 90, 70), [
                    (x, ALTURA), (x + onda, ALTURA - altura_alga), (x + 14, ALTURA)])
        # bolhas de fundo subindo devagar
        if quadro % 12 == 0:
            espalhar_bolhas(random.uniform(camera_x, camera_x + LARGURA), ALTURA + 10, 1)

    elif indice_fase == 3:
        canvas.blit(GRADIENTE_FASE3, (0, 0))
        for nx, ny, escala in [(-100, 350, 1.4), (300, 380, 1.1), (700, 340, 1.6), (1100, 390, 1.0),
                                 (1500, 350, 1.3), (1900, 380, 1.1), (2300, 340, 1.5), (2700, 390, 1.0),
                                 (3100, 350, 1.3)]:
            x = nx - camera_x * 0.1
            if -150 < x < LARGURA + 150:
                largura = int(90 * escala)
                pygame.draw.ellipse(canvas, (255, 255, 255, 255), (x, ny, largura, 40))
        for nx, ny in [(120, 60), (450, 100), (780, 50), (1100, 90), (1450, 60), (1800, 100),
                        (2150, 60), (2500, 90), (2850, 50), (3200, 90)]:
            x = nx - camera_x * 0.4
            if -100 < x < LARGURA + 100:
                pygame.draw.ellipse(canvas, BRANCO, (x, ny, 90, 38))
                pygame.draw.ellipse(canvas, BRANCO, (x + 28, ny - 16, 65, 38))
        # rajadas de vento
        for i in range(4):
            vx = (camera_x * 0.6 + i * 220 + quadro * 4) % (LARGURA + 200) - 100
            pygame.draw.line(canvas, (255, 255, 255, 120), (vx, 60 + i * 90), (vx + 60, 55 + i * 90), 2)

    elif indice_fase == 4:
        canvas.blit(GRADIENTE_FASE4, (0, 0))
        for nx, ny, escala in [(0, 380, 1.4), (350, 400, 1.1), (750, 370, 1.6), (1150, 400, 1.0),
                                 (1550, 375, 1.3), (1950, 400, 1.1), (2350, 370, 1.5), (2750, 400, 1.0),
                                 (3150, 375, 1.3)]:
            x = nx - camera_x * 0.2
            if -150 < x < LARGURA + 150:
                altura_montanha = int(120 * escala)
                pygame.draw.polygon(canvas, (35, 15, 15), [(x, 420), (x + 90, 420 - altura_montanha), (x + 180, 420)])
                pygame.draw.polygon(canvas, (255, 120, 40), [(x + 70, 420 - altura_montanha + 25),
                                                              (x + 90, 420 - altura_montanha), (x + 110, 420 - altura_montanha + 25)])
        # fumaca / cinzas subindo
        if quadro % 8 == 0:
            espalhar_particulas(random.uniform(camera_x, camera_x + LARGURA), ALTURA, (90, 70, 70), 1, gravidade=-0.05)
        if quadro % 5 == 0:
            espalhar_particulas(random.uniform(camera_x, camera_x + LARGURA), ALTURA + 10, (255, 140, 40), 1, gravidade=-0.1)

    elif indice_fase == 5:
        canvas.blit(GRADIENTE_FASE5, (0, 0))
        for nx, ny, escala in [(0, 390, 1.6), (400, 410, 1.2), (900, 380, 1.8), (1400, 410, 1.1)]:
            x = nx - camera_x * 0.2
            if -150 < x < LARGURA + 150:
                altura_montanha = int(130 * escala)
                pygame.draw.polygon(canvas, (25, 6, 10), [(x, 420), (x + 100, 420 - altura_montanha), (x + 200, 420)])
        if quadro % 6 == 0:
            espalhar_particulas(random.uniform(camera_x, camera_x + LARGURA), ALTURA, (255, 120, 60), 1, gravidade=-0.1)


# ---------------------------------------------------------
# PLATAFORMAS FIXAS (visual muda conforme o "estilo" da fase)
# ---------------------------------------------------------
def desenhar_plataformas(canvas, camera_x, plataformas, estilo="grama"):
    for plat in plataformas:
        x = plat.x - camera_x
        if x + plat.width < 0 or x > LARGURA:
            continue

        if estilo == "grama":
            corpo = pygame.Rect(x, plat.y + 8, plat.width, plat.height - 8)
            pygame.draw.rect(canvas, (150, 100, 60), corpo)
            pygame.draw.rect(canvas, (86, 200, 90), (x, plat.y, plat.width, 12))
            pygame.draw.rect(canvas, (60, 160, 65), (x, plat.y + 10, plat.width, 3))
            for tufo_x in range(0, plat.width, 14):
                pygame.draw.line(canvas, (50, 140, 55), (x + tufo_x + 3, plat.y + 2), (x + tufo_x + 1, plat.y - 4), 2)
                pygame.draw.line(canvas, (50, 140, 55), (x + tufo_x + 7, plat.y + 2), (x + tufo_x + 8, plat.y - 5), 2)

        elif estilo == "coral":
            corpo = pygame.Rect(x, plat.y + 8, plat.width, plat.height - 8)
            pygame.draw.rect(canvas, (200, 170, 140), corpo)
            pygame.draw.rect(canvas, (255, 127, 80), (x, plat.y, plat.width, 12))
            pygame.draw.rect(canvas, (200, 90, 50), (x, plat.y + 10, plat.width, 3))
            for tx in range(0, plat.width, 18):
                pygame.draw.circle(canvas, (255, 170, 130), (int(x + tx + 6), plat.y + 2), 5)
                pygame.draw.circle(canvas, (240, 100, 130), (int(x + tx + 12), plat.y - 2), 4)

        elif estilo == "nuvem":
            corpo = pygame.Rect(x, plat.y, plat.width, plat.height)
            pygame.draw.ellipse(canvas, BRANCO, corpo)
            pygame.draw.ellipse(canvas, (225, 235, 250), corpo, 3)
            for tx in range(10, plat.width - 10, 22):
                pygame.draw.circle(canvas, BRANCO, (int(x + tx), plat.y + 4), 12)

        elif estilo == "rocha":
            corpo = pygame.Rect(x, plat.y + 6, plat.width, plat.height - 6)
            pygame.draw.rect(canvas, (55, 45, 45), corpo)
            pygame.draw.rect(canvas, (90, 75, 70), (x, plat.y, plat.width, 10))
            for tx in range(0, plat.width, 20):
                pygame.draw.line(canvas, (255, 110, 30), (x + tx, plat.y + 8), (x + tx + 10, plat.y + 16), 2)

        elif estilo == "arena":
            corpo = pygame.Rect(x, plat.y + 6, plat.width, plat.height - 6)
            pygame.draw.rect(canvas, (40, 25, 30), corpo)
            pygame.draw.rect(canvas, (80, 40, 45), (x, plat.y, plat.width, 10))
            for tx in range(0, plat.width, 26):
                pygame.draw.line(canvas, (120, 40, 30), (x + tx, plat.y + 2), (x + tx + 6, plat.y + 9), 2)


# ===========================================================
# FASE 1 - CAMPO (a fase classica)
# ===========================================================
def criar_fase_1():
    TERRENO = 400
    ANDAR_1, ANDAR_2, ANDAR_3 = 320, 260, 195
    GAP, ALT_BLOCO = 60, 30
    ALT_B1 = ANDAR_1 - GAP - ALT_BLOCO
    ALT_B3 = ANDAR_3 - GAP - ALT_BLOCO
    ALT_B2 = ANDAR_2 - GAP - ALT_BLOCO

    plataformas = [
        pygame.Rect(0, TERRENO, 3400, 50),
        pygame.Rect(280, ANDAR_1, 150, 20),
        pygame.Rect(820, ANDAR_1, 120, 20),
        pygame.Rect(1620, ANDAR_2, 130, 20),
        pygame.Rect(1900, ANDAR_1, 130, 20),
        pygame.Rect(2420, ANDAR_3, 110, 20),
        pygame.Rect(2900, ANDAR_2, 140, 20),
    ]
    plataformas_moveis = [
        PlataformaMovel(1050, ANDAR_2 + 40, 90, 20, 1050, 1500, 2.2),
        PlataformaMovel(2100, ANDAR_2 - 30, 90, 20, 2100, 2320, 2.8),
        PlataformaMovel(2600, ANDAR_2 - 30, 100, 20, 2600, 2800, 2.5),
    ]
    perigos = [
        pygame.Rect(560, 388, 60, 12), pygame.Rect(1300, 388, 70, 12),
        pygame.Rect(2020, 388, 60, 12), pygame.Rect(3070, 388, 70, 12),
    ]
    posicoes_blocos = [
        (330, ALT_B1), (370, ALT_B1), (410, ALT_B1),
        (850, ALT_B1), (890, ALT_B1),
        (1930, ALT_B1), (1970, ALT_B1), (2010, ALT_B1),
        (2440, ALT_B3), (2480, ALT_B3),
        (2930, ALT_B2), (2970, ALT_B2), (3010, ALT_B2),
    ]
    blocos = [criar_bloco(bx, by, i % 3 == 0) for i, (bx, by) in enumerate(posicoes_blocos)]

    moedas = []
    for plat in plataformas[1:]:
        moedas.append(pygame.Rect(plat.x + plat.width // 2 - 10, plat.y - 35, 20, 20))
    moedas += [pygame.Rect(180, 350, 20, 20), pygame.Rect(650, 350, 20, 20),
               pygame.Rect(1350, 350, 20, 20), pygame.Rect(2750, 350, 20, 20),
               pygame.Rect(3200, 350, 20, 20)]

    inimigos = [
        criar_inimigo_chao(850, 370, 780, 1020, 2.5),
        criar_inimigo_chao(1950, 370, 1850, 2150, 3.5),
        criar_inimigo_chao(2950, 370, 2870, 3170, 3),
        criar_inimigo_voador(1750, 150, 1700, 2050, 3, 150, 0.0),
        criar_inimigo_voador(2450, 120, 2350, 2650, 3.5, 120, 1.5),
    ]
    powerups = [
        {"rect": pygame.Rect(860, ANDAR_1 - 55, 26, 26), "tipo": "pulo_duplo", "coletado": False},
        {"rect": pygame.Rect(2450, ANDAR_3 - 60, 26, 26), "tipo": "turbo", "coletado": False},
    ]
    bandeira = pygame.Rect(3250, 250, 15, 150)

    return {
        "nome": "CAMPO", "estilo": "grama", "perigo_estilo": "espinho",
        "cor_bloco": (200, 120, 70), "cor_bloco_escuro": (150, 85, 45),
        "modo_fisica": "normal", "plataformas": plataformas,
        "plataformas_moveis": plataformas_moveis, "perigos": perigos, "blocos": blocos,
        "moedas": moedas, "inimigos": inimigos, "powerups": powerups, "bandeira": bandeira,
        "fim_fase_x": 3300, "ponto_inicio": (60, 100),
    }


# ===========================================================
# FASE 2 - OCEANO (aquatica: peixes e tubaroes)
# ===========================================================
def criar_fase_2():
    TERRENO = 400
    ANDAR_1, ANDAR_2, ANDAR_3 = 330, 260, 180

    plataformas = [
        pygame.Rect(0, TERRENO, 3400, 50),
        pygame.Rect(260, ANDAR_2, 130, 20),
        pygame.Rect(700, ANDAR_1, 120, 20),
        pygame.Rect(1050, ANDAR_3, 110, 20),
        pygame.Rect(1450, ANDAR_2, 140, 20),
        pygame.Rect(1850, ANDAR_1, 120, 20),
        pygame.Rect(2250, ANDAR_3, 110, 20),
        pygame.Rect(2650, ANDAR_2, 140, 20),
        pygame.Rect(3050, ANDAR_1, 150, 20),
    ]
    plataformas_moveis = [
        PlataformaMovel(500, 150, 80, 18, None, None, 1.6, cor=(255, 170, 130), cor_escura=(200, 100, 60),
                         min_y=120, max_y=260),
        PlataformaMovel(1650, 120, 80, 18, None, None, 1.8, cor=(255, 170, 130), cor_escura=(200, 100, 60),
                         min_y=100, max_y=300),
        PlataformaMovel(2450, 150, 90, 18, None, None, 1.5, cor=(255, 170, 130), cor_escura=(200, 100, 60),
                         min_y=110, max_y=290),
    ]
    perigos = [  # ouricos-do-mar no fundo
        pygame.Rect(560, 388, 50, 14), pygame.Rect(1300, 388, 60, 14),
        pygame.Rect(2050, 388, 50, 14), pygame.Rect(2900, 388, 60, 14),
    ]
    posicoes_blocos = [
        (700, ANDAR_1 - 60), (740, ANDAR_1 - 60),
        (1850, ANDAR_1 - 60), (1890, ANDAR_1 - 60), (1930, ANDAR_1 - 60),
        (3050, ANDAR_1 - 60), (3090, ANDAR_1 - 60),
    ]
    blocos = [criar_bloco(bx, by, i % 2 == 0, largura=36, altura=28) for i, (bx, by) in enumerate(posicoes_blocos)]

    moedas = []
    for plat in plataformas[1:]:
        moedas.append(pygame.Rect(plat.x + plat.width // 2 - 10, plat.y - 40, 20, 20))
    moedas += [pygame.Rect(150, 300, 20, 20), pygame.Rect(950, 200, 20, 20),
               pygame.Rect(1650, 150, 20, 20), pygame.Rect(2350, 200, 20, 20),
               pygame.Rect(2950, 150, 20, 20)]

    inimigos = [
        criar_peixe(500, 250, 400, 900, 2.0, 250, 0.0),
        criar_peixe(1200, 200, 1050, 1550, 2.5, 200, 1.0),
        criar_peixe(2100, 230, 1950, 2450, 2.2, 230, 2.0),
        criar_tubarao(900, 340, 750, 1400, 2.0),
        criar_tubarao(2500, 340, 2300, 3050, 2.4),
    ]
    powerups = [
        {"rect": pygame.Rect(1080, ANDAR_3 - 55, 26, 26), "tipo": "pulo_duplo", "coletado": False},
        {"rect": pygame.Rect(2280, ANDAR_3 - 55, 26, 26), "tipo": "turbo", "coletado": False},
    ]
    bandeira = pygame.Rect(3280, 220, 15, 150)

    return {
        "nome": "OCEANO", "estilo": "coral", "perigo_estilo": "ourico",
        "cor_bloco": (150, 200, 210), "cor_bloco_escuro": (100, 150, 165),
        "modo_fisica": "agua", "plataformas": plataformas,
        "plataformas_moveis": plataformas_moveis, "perigos": perigos, "blocos": blocos,
        "moedas": moedas, "inimigos": inimigos, "powerups": powerups, "bandeira": bandeira,
        "fim_fase_x": 3330, "ponto_inicio": (60, 150),
    }


# ===========================================================
# FASE 3 - CEUS (plataformas de nuvem, inimigos voadores/eletricos)
# ===========================================================
def criar_fase_3():
    ANDAR_1, ANDAR_2, ANDAR_3, ANDAR_4 = 350, 280, 210, 140

    plataformas = [
        pygame.Rect(0, ANDAR_1, 220, 24),
        pygame.Rect(320, ANDAR_2, 130, 22),
        pygame.Rect(560, ANDAR_3, 110, 22),
        pygame.Rect(820, ANDAR_1, 130, 22),
        pygame.Rect(1100, ANDAR_2, 110, 22),
        pygame.Rect(1350, ANDAR_4, 110, 22),
        pygame.Rect(1620, ANDAR_2, 130, 22),
        pygame.Rect(1900, ANDAR_1, 120, 22),
        pygame.Rect(2180, ANDAR_3, 110, 22),
        pygame.Rect(2450, ANDAR_2, 130, 22),
        pygame.Rect(2750, ANDAR_1, 130, 22),
        pygame.Rect(3050, ANDAR_2, 200, 22),
    ]
    plataformas_moveis = [
        PlataformaMovel(1230, ANDAR_2, 90, 20, 1230, 1560, 2.4, cor=BRANCO, cor_escura=(220, 225, 240)),
        PlataformaMovel(2320, ANDAR_1, 90, 20, 2320, 2700, 2.6, cor=BRANCO, cor_escura=(220, 225, 240)),
    ]
    perigos = [  # nuvens de raio, fixas no ar entre plataformas
        pygame.Rect(480, 300, 40, 40), pygame.Rect(1480, 240, 40, 40),
        pygame.Rect(2080, 250, 40, 40), pygame.Rect(2900, 300, 40, 40),
    ]
    posicoes_blocos = [
        (830, ANDAR_1 - 60), (870, ANDAR_1 - 60),
        (1910, ANDAR_1 - 60), (1950, ANDAR_1 - 60), (1990, ANDAR_1 - 60),
        (2760, ANDAR_1 - 60), (2800, ANDAR_1 - 60),
    ]
    blocos = [criar_bloco(bx, by, i % 2 == 0) for i, (bx, by) in enumerate(posicoes_blocos)]

    moedas = []
    for plat in plataformas:
        moedas.append(pygame.Rect(plat.x + plat.width // 2 - 10, plat.y - 35, 20, 20))
    moedas += [pygame.Rect(1360, 100, 20, 20), pygame.Rect(2190, 170, 20, 20)]

    inimigos = [
        criar_inimigo_voador(600, 180, 500, 850, 3.0, 180, 0.0),
        criar_inimigo_voador(1400, 100, 1300, 1650, 3.2, 100, 1.2),
        criar_inimigo_voador(2500, 160, 2400, 2800, 3.4, 160, 2.4),
        criar_eletrico(950, 230, 850, 1150, 3.6, 230, 0.0),
        criar_eletrico(1950, 150, 1850, 2250, 4.0, 150, 1.5),
        criar_eletrico(3100, 180, 3000, 3300, 3.8, 180, 3.0),
    ]
    powerups = [
        {"rect": pygame.Rect(1360, ANDAR_4 - 50, 26, 26), "tipo": "pulo_duplo", "coletado": False},
        {"rect": pygame.Rect(2460, ANDAR_2 - 55, 26, 26), "tipo": "turbo", "coletado": False},
    ]
    bandeira = pygame.Rect(3350, ANDAR_2 - 150, 15, 150)

    return {
        "nome": "CEUS", "estilo": "nuvem", "perigo_estilo": "raio",
        "cor_bloco": (235, 235, 245), "cor_bloco_escuro": (190, 190, 210),
        "modo_fisica": "normal", "plataformas": plataformas,
        "plataformas_moveis": plataformas_moveis, "perigos": perigos, "blocos": blocos,
        "moedas": moedas, "inimigos": inimigos, "powerups": powerups, "bandeira": bandeira,
        "fim_fase_x": 3400, "ponto_inicio": (30, ANDAR_1 - 60),
    }


# ===========================================================
# FASE 4 - VULCAO (pedras, lava e o novo inimigo de lava)
# ===========================================================
def criar_fase_4():
    TERRENO = 400
    ANDAR_1, ANDAR_2, ANDAR_3 = 330, 260, 190

    plataformas = [
        pygame.Rect(0, TERRENO, 500, 50),
        pygame.Rect(620, TERRENO, 300, 50),
        pygame.Rect(300, ANDAR_1, 130, 20),
        pygame.Rect(1050, TERRENO, 260, 50),
        pygame.Rect(900, ANDAR_2, 110, 20),
        pygame.Rect(1450, TERRENO, 350, 50),
        pygame.Rect(1650, ANDAR_1, 120, 20),
        pygame.Rect(1950, ANDAR_3, 110, 20),
        pygame.Rect(2050, TERRENO, 250, 50),
        pygame.Rect(2450, TERRENO, 400, 50),
        pygame.Rect(2600, ANDAR_1, 130, 20),
        pygame.Rect(3050, TERRENO, 350, 50),
    ]
    # plataformas que sobem e descem dentro da lava (precisa de timing)
    plataformas_moveis = [
        PlataformaMovel(500, 340, 100, 20, None, None, 1.6, cor=(90, 75, 70), cor_escura=(50, 40, 40),
                         min_y=330, max_y=395),
        PlataformaMovel(920, 340, 100, 20, None, None, 1.8, cor=(90, 75, 70), cor_escura=(50, 40, 40),
                         min_y=330, max_y=395),
        PlataformaMovel(1800, 340, 100, 20, None, None, 1.7, cor=(90, 75, 70), cor_escura=(50, 40, 40),
                         min_y=330, max_y=395),
        PlataformaMovel(2300, 340, 100, 20, None, None, 1.9, cor=(90, 75, 70), cor_escura=(50, 40, 40),
                         min_y=330, max_y=395),
    ]
    # lava no chao (poços entre as plataformas de rocha continua)
    perigos = [
        pygame.Rect(500, 425, 120, 25), pygame.Rect(920, 425, 130, 25),
        pygame.Rect(1310, 425, 140, 25), pygame.Rect(1800, 425, 130, 25),
        pygame.Rect(2300, 425, 150, 25), pygame.Rect(2850, 425, 130, 25),
    ]
    posicoes_blocos = [
        (300, ANDAR_1 - 60), (340, ANDAR_1 - 60),
        (1650, ANDAR_1 - 60), (1690, ANDAR_1 - 60),
        (2600, ANDAR_1 - 60), (2640, ANDAR_1 - 60), (2680, ANDAR_1 - 60),
    ]
    blocos = [criar_bloco(bx, by, True) for bx, by in posicoes_blocos]

    moedas = []
    for plat in plataformas:
        moedas.append(pygame.Rect(plat.x + plat.width // 2 - 10, plat.y - 35, 20, 20))
    moedas += [pygame.Rect(1970, 150, 20, 20), pygame.Rect(2680, 200, 20, 20)]

    inimigos = [
        criar_lava_inimigo(700, 375, 630, 900, 1.6),
        criar_lava_inimigo(1150, 375, 1060, 1290, 1.8),
        criar_lava_inimigo(2200, 375, 2060, 2440, 2.0),
        criar_lava_inimigo(2900, 375, 2460, 2840, 1.7),
        criar_inimigo_chao(1700, 370, 1650, 1770, 2.6),
        criar_inimigo_voador(2000, 130, 1900, 2400, 3.4, 130, 0.5),
    ]
    powerups = [
        {"rect": pygame.Rect(900, ANDAR_2 - 55, 26, 26), "tipo": "turbo", "coletado": False},
        {"rect": pygame.Rect(1955, ANDAR_3 - 55, 26, 26), "tipo": "pulo_duplo", "coletado": False},
    ]
    bandeira = pygame.Rect(3350, 250, 15, 150)

    return {
        "nome": "VULCAO", "estilo": "rocha", "perigo_estilo": "lava",
        "cor_bloco": (110, 95, 90), "cor_bloco_escuro": (70, 55, 50),
        "modo_fisica": "normal", "plataformas": plataformas,
        "plataformas_moveis": plataformas_moveis, "perigos": perigos, "blocos": blocos,
        "moedas": moedas, "inimigos": inimigos, "powerups": powerups, "bandeira": bandeira,
        "fim_fase_x": 3400, "ponto_inicio": (60, 100),
    }


CRIADORES_DE_FASE = {1: criar_fase_1, 2: criar_fase_2, 3: criar_fase_3, 4: criar_fase_4}
NOMES_FASE = {1: "CAMPO", 2: "OCEANO", 3: "CEUS", 4: "VULCAO", 5: "COVIL DO TIGRE"}


# ===========================================================
# FASE 5 - CHEFE FINAL: TIGRE GIGANTE
# ===========================================================
def criar_fase_5():
    CHAO = 400
    plataformas = [
        pygame.Rect(0, CHAO, 400, 50),
        pygame.Rect(500, CHAO, 2600, 50),
        pygame.Rect(3200, CHAO, 400, 50),
    ]
    return {
        "nome": "COVIL DO TIGRE", "estilo": "arena", "perigo_estilo": "espinho",
        "cor_bloco": (60, 40, 40), "cor_bloco_escuro": (35, 20, 20),
        "modo_fisica": "normal", "plataformas": plataformas,
        "plataformas_moveis": [], "perigos": [], "blocos": [],
        "moedas": [], "inimigos": [], "powerups": [], "bandeira": None,
        "fim_fase_x": 4000, "ponto_inicio": (700, 320),
    }


VIDA_MAXIMA_TIGRE = 8


class TigreGigante:
    """Chefe final: um tigre gigante com barra de vida. Alterna entre
    patrulhar, avisar um ataque (telegraph), atacar (avanco/rugido) e
    ficar vulneravel por um instante logo apos o ataque -- e so nesse
    instante que pular na cabeca dele causa dano de verdade."""

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.largura = 140
        self.altura = 100
        self.direcao = -1
        self.vida = VIDA_MAXIMA_TIGRE
        self.vida_max = VIDA_MAXIMA_TIGRE
        self.estado = "patrulha"
        self.timer_estado = 90
        self.vel_x = 0
        self.vulneravel = False
        self.dano_flash = 0
        self.derrotado = False
        self.entrada_concluida = False
        self.rugido_empurrou = False
        self.arena_min_x = 560
        self.arena_max_x = 3140

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.largura, self.altura)

    def rect_cabeca(self):
        # a "cabeca" (ponto vulneravel) fica na frente de onde o tigre olha
        largura_cabeca = 46
        cx = self.x + (self.largura - largura_cabeca) if self.direcao == 1 else self.x
        return pygame.Rect(int(cx), int(self.y - 6), largura_cabeca, 46)

    def agressividade(self):
        # fica mais rapido e agressivo com pouca vida
        return 1.0 + (1.0 - self.vida / self.vida_max) * 0.9

    def atualizar(self, gato):
        if self.derrotado:
            return

        agr = self.agressividade()

        if self.estado == "patrulha":
            self.vel_x = 1.6 * agr * self.direcao
            self.x += self.vel_x
            if self.x < self.arena_min_x:
                self.x = self.arena_min_x
                self.direcao = 1
            elif self.x + self.largura > self.arena_max_x:
                self.x = self.arena_max_x - self.largura
                self.direcao = -1
            if abs(gato.x - self.x) < 380:
                self.direcao = 1 if gato.x > self.x else -1
            self.timer_estado -= 1
            if self.timer_estado <= 0:
                proximo = random.choice(["telegraph_carga", "telegraph_rugido"])
                self.estado = proximo
                self.timer_estado = 45
                self.direcao = 1 if gato.x > self.x else -1

        elif self.estado == "telegraph_carga":
            self.timer_estado -= 1
            if self.timer_estado % 8 < 4:
                pass  # tremor visual tratado no desenho
            if self.timer_estado <= 0:
                self.estado = "carga"
                self.timer_estado = 55

        elif self.estado == "carga":
            self.vel_x = 9.5 * agr * self.direcao
            self.x += self.vel_x
            self.x = max(self.arena_min_x, min(self.x, self.arena_max_x - self.largura))
            if random.random() < 0.5:
                espalhar_particulas(self.x + (self.largura if self.direcao > 0 else 0), self.y + self.altura,
                                     (150, 120, 90), 2, gravidade=0.3)
            self.timer_estado -= 1
            if self.timer_estado <= 0 or self.x <= self.arena_min_x or self.x + self.largura >= self.arena_max_x:
                self.estado = "atordoado"
                self.timer_estado = 55
                self.vulneravel = True

        elif self.estado == "telegraph_rugido":
            self.timer_estado -= 1
            if self.timer_estado <= 0:
                self.estado = "rugido"
                self.timer_estado = 30
                self.rugido_empurrou = False

        elif self.estado == "rugido":
            self.timer_estado -= 1
            if not self.rugido_empurrou and self.timer_estado == 15:
                self.rugido_empurrou = True
                distancia = gato.x - (self.x + self.largura / 2)
                if abs(distancia) < 260:
                    empurrao = 6 if distancia > 0 else -6
                    gato.x += empurrao * 8
                    espalhar_particulas(gato.x, gato.y, (255, 255, 255), 6)
            if self.timer_estado <= 0:
                self.estado = "atordoado"
                self.timer_estado = 40
                self.vulneravel = True

        elif self.estado == "atordoado":
            self.timer_estado -= 1
            if self.timer_estado <= 0:
                self.vulneravel = False
                self.estado = "patrulha"
                self.timer_estado = random.randint(70, 110)

        if self.dano_flash > 0:
            self.dano_flash -= 1

        # colisao corpo-a-corpo (contato fora da janela vulneravel machuca)
        gato_rect = gato.rect()
        if gato_rect.colliderect(self.rect()) and gato.invencivel == 0:
            cabeca = self.rect_cabeca()
            pisando = self.vulneravel and gato.vel_y > 0 and gato_rect.colliderect(cabeca) and \
                gato_rect.bottom - gato.vel_y <= cabeca.top + 16
            if pisando:
                self.receber_dano()
                gato.vel_y = PULO_FORCA * 0.75
                espalhar_particulas(cabeca.centerx, cabeca.centery, (255, 220, 150), 16)
            else:
                gato.perder_vida((700, 320))

    def receber_dano(self):
        if self.vida <= 0:
            return
        self.vida -= 1
        self.dano_flash = 18
        tocar("stomp")
        if self.vida <= 0:
            self.derrotado = True
            self.estado = "derrotado"
            tocar("vencer")

    def desenhar(self, canvas, camera_x, quadro):
        if self.derrotado:
            return
        x = self.x - camera_x
        if x + self.largura < -50 or x > LARGURA + 50:
            return

        tremor_x = 0
        if self.estado == "telegraph_carga":
            tremor_x = random.uniform(-3, 3)
        piscar = self.dano_flash > 0 and self.dano_flash % 6 < 3

        cor_pelo = (255, 255, 255) if piscar else (255, 150, 40)
        cor_pelo_escuro = (255, 255, 255) if piscar else (200, 100, 20)
        cor_listra = (60, 40, 20) if not piscar else (200, 200, 200)

        cx = x + tremor_x
        cy = self.y

        # sombra
        sombra = pygame.Surface((self.largura, 16), pygame.SRCALPHA)
        pygame.draw.ellipse(sombra, (0, 0, 0, 90), sombra.get_rect())
        canvas.blit(sombra, (cx, cy + self.altura - 6))

        # cauda balancando
        balanco = 12 * math.sin(quadro * 0.08)
        cauda_x = cx + self.largura - 4 if self.direcao == 1 else cx + 4
        sinal_cauda = -1 if self.direcao == 1 else 1
        pygame.draw.line(canvas, cor_pelo_escuro, (cauda_x, cy + 30),
                          (cauda_x + sinal_cauda * (50 + balanco), cy + 5), 10)

        # corpo
        corpo = pygame.Rect(cx, cy + 20, self.largura, self.altura - 30)
        pygame.draw.ellipse(canvas, cor_pelo, corpo)
        pygame.draw.ellipse(canvas, cor_pelo_escuro, corpo, 3)
        for i, lx in enumerate(range(15, self.largura - 15, 20)):
            pygame.draw.line(canvas, cor_listra, (cx + lx, cy + 24), (cx + lx - 8, cy + 20 + self.altura - 34), 4)

        # patas
        for dx in (12, self.largura - 40):
            pata = pygame.Rect(cx + dx, cy + self.altura - 22, 28, 22)
            pygame.draw.ellipse(canvas, cor_pelo_escuro, pata)

        # cabeca
        cabeca_r = self.rect_cabeca()
        hx = cabeca_r.x - camera_x + tremor_x
        hy = cabeca_r.y
        pygame.draw.ellipse(canvas, cor_pelo, (hx, hy, cabeca_r.width, cabeca_r.height))
        pygame.draw.ellipse(canvas, cor_pelo_escuro, (hx, hy, cabeca_r.width, cabeca_r.height), 3)
        for lx in range(6, cabeca_r.width - 6, 10):
            pygame.draw.line(canvas, cor_listra, (hx + lx, hy + 4), (hx + lx - 3, hy + cabeca_r.height - 6), 3)

        # orelhas
        for dx in (2, cabeca_r.width - 14):
            pygame.draw.polygon(canvas, cor_pelo_escuro, [
                (hx + dx, hy + 6), (hx + dx + 6, hy - 10), (hx + dx + 13, hy + 6)])

        # olhos ferozes
        olho_y = hy + 16
        for dx in (10, cabeca_r.width - 18):
            cor_olho = VERMELHO if self.estado in ("telegraph_carga", "carga", "telegraph_rugido", "rugido") else (255, 210, 60)
            pygame.draw.ellipse(canvas, cor_olho, (hx + dx, olho_y, 10, 7))
            pygame.draw.circle(canvas, PRETO, (int(hx + dx + 5), int(olho_y + 3)), 2)

        # presas
        boca_y = hy + cabeca_r.height - 10
        for dx in (8, cabeca_r.width - 16):
            pygame.draw.polygon(canvas, BRANCO, [
                (hx + dx, boca_y), (hx + dx + 6, boca_y), (hx + dx + 3, boca_y + 12)])

        # marca de "vulneravel" (uma estrela pulsando sobre a cabeca)
        if self.vulneravel:
            pulso = 4 * math.sin(quadro * 0.3)
            centro = (int(hx + cabeca_r.width / 2), int(hy - 18 + pulso))
            pygame.draw.circle(canvas, (255, 255, 120), centro, 8)
            pygame.draw.circle(canvas, (255, 200, 40), centro, 8, 2)

        # aviso de investida
        if self.estado == "telegraph_carga" and quadro % 10 < 6:
            aviso = FONTE_MEDIA.render("!", True, VERMELHO)
            canvas.blit(aviso, (hx + cabeca_r.width / 2 - 5, hy - 40))
        if self.estado == "telegraph_rugido" and quadro % 10 < 6:
            aviso = FONTE_PEQUENA.render("RUGIDO!", True, (255, 220, 120))
            canvas.blit(aviso, (hx - 10, hy - 30))

    def desenhar_barra_vida(self, canvas):
        largura_barra = 420
        x0 = LARGURA // 2 - largura_barra // 2
        y0 = 18
        painel = pygame.Surface((largura_barra + 20, 46), pygame.SRCALPHA)
        pygame.draw.rect(painel, (20, 10, 10, 170), painel.get_rect(), border_radius=10)
        canvas.blit(painel, (x0 - 10, y0 - 8))

        titulo = FONTE_PEQUENA.render("TIGRE GIGANTE", True, (255, 210, 150))
        canvas.blit(titulo, (x0, y0 - 6))

        y_barra = y0 + 14
        pygame.draw.rect(canvas, (60, 20, 20), (x0, y_barra, largura_barra, 18), border_radius=6)
        proporcao = max(0, self.vida) / self.vida_max
        largura_vida = int(largura_barra * proporcao)
        if largura_vida > 0:
            cor = VERMELHO if proporcao > 0.3 else (255, 140, 40)
            pygame.draw.rect(canvas, cor, (x0, y_barra, largura_vida, 18), border_radius=6)
        pygame.draw.rect(canvas, BRANCO, (x0, y_barra, largura_barra, 18), 2, border_radius=6)


# ===========================================================
# CARREGAMENTO DE AUDIO (efeitos + uma trilha original por fase)
# ===========================================================
def carregar_audio():
    if not SOM_ATIVADO:
        return

    SONS["pulo"] = criar_som(gerar_tom(500, 0.12, 0.35, "quadrada"))
    SONS["pulo_duplo"] = criar_som(gerar_melodia([(500, 0.08), (750, 0.1)], 0.35, "quadrada"))
    SONS["powerup"] = criar_som(gerar_melodia([(660, 0.08), (880, 0.08), (1180, 0.14)], 0.4, "senoide"))
    SONS["moeda"] = criar_som(gerar_melodia([(880, 0.06), (1318, 0.10)], 0.35, "senoide"))
    SONS["quebrar"] = criar_som(gerar_ruido(0.18, 0.4))
    SONS["stomp"] = criar_som(gerar_melodia([(400, 0.05), (200, 0.08)], 0.4, "quadrada"))
    SONS["perder_vida"] = criar_som(gerar_tom(150, 0.35, 0.4, "serra"))
    SONS["vencer"] = criar_som(gerar_melodia(
        [(523, 0.15), (659, 0.15), (784, 0.15), (1047, 0.35)], 0.4, "quadrada"))
    SONS["perder_jogo"] = criar_som(gerar_melodia(
        [(392, 0.2), (349, 0.2), (294, 0.2), (196, 0.5)], 0.4, "triangular"))
    SONS["fase_completa"] = criar_som(gerar_melodia(
        [(523, 0.12), (659, 0.12), (784, 0.12), (1047, 0.12), (1318, 0.3)], 0.4, "senoide"))

    # ---- FASE 1: CAMPO -- clima de aventura classica (ja existente) ----
    frase_a = [(329.63, 0.18), (392.00, 0.18), (440.00, 0.18), (523.25, 0.30),
               (440.00, 0.15), (392.00, 0.15), (329.63, 0.45)]
    frase_b = [(440.00, 0.15), (523.25, 0.15), (587.33, 0.15), (523.25, 0.15),
               (440.00, 0.15), (392.00, 0.15), (440.00, 0.30), (0, 0.1),
               (493.88, 0.15), (523.25, 0.15), (587.33, 0.30)]
    frase_c = [(392.00, 0.18), (440.00, 0.18), (523.25, 0.18), (587.33, 0.18),
               (659.25, 0.5), (523.25, 0.25), (392.00, 0.6)]
    baixo_1 = [(110.00, 0.36), (164.81, 0.36), (110.00, 0.36), (164.81, 0.36),
               (130.81, 0.36), (196.00, 0.36), (130.81, 0.36), (196.00, 0.36),
               (98.00, 0.36), (146.83, 0.36), (98.00, 0.36), (146.83, 0.36),
               (146.83, 0.36), (220.00, 0.36), (146.83, 0.36), (220.00, 0.36),
               (110.00, 0.72), (110.00, 0.72)]
    lead1 = gerar_melodia(frase_a + frase_b + frase_c, 0.28, "triangular")
    baixo1 = gerar_melodia(baixo_1, 0.22, "triangular")
    MUSICAS[1] = criar_som(mixar(lead1, baixo1, volume_total=0.8))

    # ---- FASE 2: OCEANO -- lenta, ondulante, senoides suaves ----
    onda_a = [(261.63, 0.4), (329.63, 0.4), (392.00, 0.6), (0, 0.1),
              (349.23, 0.4), (293.66, 0.4), (261.63, 0.6)]
    onda_b = [(392.00, 0.3), (440.00, 0.3), (523.25, 0.5), (0, 0.1),
              (466.16, 0.3), (392.00, 0.3), (349.23, 0.6)]
    baixo_agua = [(87.31, 0.8), (110.00, 0.8), (98.00, 0.8), (73.42, 0.8),
                  (87.31, 0.8), (110.00, 0.8), (65.41, 1.2)]
    lead2 = gerar_melodia(onda_a + onda_b, 0.22, "senoide")
    baixo2 = gerar_melodia(baixo_agua, 0.18, "senoide")
    MUSICAS[2] = criar_som(mixar(lead2, baixo2, volume_total=0.75))

    # ---- FASE 3: CEUS -- leve, rapida, arpejos altos ----
    ceu_a = [(523.25, 0.12), (659.25, 0.12), (784.00, 0.12), (1046.50, 0.2),
             (784.00, 0.12), (659.25, 0.12), (523.25, 0.24)]
    ceu_b = [(587.33, 0.12), (698.46, 0.12), (880.00, 0.12), (1174.66, 0.2),
             (880.00, 0.12), (698.46, 0.12), (587.33, 0.24)]
    baixo_ceu = [(196.00, 0.24), (261.63, 0.24), (196.00, 0.24), (261.63, 0.24),
                 (220.00, 0.24), (293.66, 0.24), (220.00, 0.24), (293.66, 0.24)]
    lead3 = gerar_melodia((ceu_a + ceu_b) * 1, 0.24, "triangular")
    baixo3 = gerar_melodia(baixo_ceu * 2, 0.16, "quadrada")
    MUSICAS[3] = criar_som(mixar(lead3, baixo3, volume_total=0.75))

    # ---- FASE 4: VULCAO -- tensa, ritmo martelado, onda quadrada ----
    vulcao_a = [(196.00, 0.14), (196.00, 0.14), (233.08, 0.14), (196.00, 0.14),
                (174.61, 0.14), (196.00, 0.14), (155.56, 0.28), (0, 0.08)]
    vulcao_b = [(233.08, 0.14), (233.08, 0.14), (261.63, 0.14), (233.08, 0.14),
                (207.65, 0.14), (233.08, 0.14), (185.00, 0.28), (0, 0.08)]
    baixo_vulcao = [(65.41, 0.18), (65.41, 0.18), (77.78, 0.18), (65.41, 0.18)] * 2
    lead4 = gerar_melodia((vulcao_a + vulcao_b) * 1, 0.3, "quadrada")
    baixo4 = gerar_melodia(baixo_vulcao, 0.26, "serra")
    MUSICAS[4] = criar_som(mixar(lead4, baixo4, volume_total=0.85))

    # ---- FASE 5: CHEFE FINAL -- epica, dramatica, tom menor ----
    chefe_a = [(220.00, 0.16), (261.63, 0.16), (293.66, 0.16), (329.63, 0.3),
               (293.66, 0.16), (261.63, 0.16), (220.00, 0.3), (0, 0.1)]
    chefe_b = [(207.65, 0.16), (246.94, 0.16), (277.18, 0.16), (311.13, 0.3),
               (277.18, 0.16), (246.94, 0.16), (207.65, 0.4), (0, 0.1)]
    baixo_chefe = [(55.00, 0.2), (55.00, 0.2), (61.74, 0.2), (55.00, 0.2),
                   (49.00, 0.2), (55.00, 0.2), (41.20, 0.4)]
    lead5 = gerar_melodia((chefe_a + chefe_b) * 1, 0.3, "serra")
    baixo5 = gerar_melodia(baixo_chefe * 2, 0.28, "triangular")
    MUSICAS[5] = criar_som(mixar(lead5, baixo5, volume_total=0.85))

    # ---- TEMA FINAL / CREDITOS -- triste, mas com um fio de esperanca ----
    # Uma composicao original e lenta, em La menor, inspirada no clima
    # introspectivo de baladas melancolicas -- nenhuma melodia real e
    # copiada, so o "sentimento" (poucas notas, muito espaco, resolucao
    # mais luminosa no final).
    tema_a = [(220.00, 0.7), (0, 0.1), (261.63, 0.7), (0, 0.1),
              (329.63, 1.0), (0, 0.25), (293.66, 0.7), (0, 0.1),
              (261.63, 0.7), (0, 0.1), (220.00, 1.1), (0, 0.35)]
    tema_b = [(246.94, 0.7), (0, 0.1), (293.66, 0.7), (0, 0.1),
              (349.23, 1.0), (0, 0.25), (329.63, 0.7), (0, 0.1),
              (293.66, 0.7), (0, 0.1), (261.63, 1.1), (0, 0.35)]
    tema_resolucao = [(261.63, 0.8), (329.63, 0.8), (392.00, 1.0),
                       (440.00, 1.6), (0, 0.4)]
    baixo_tema = [(110.00, 1.4), (0, 0.15), (130.81, 1.4), (0, 0.15),
                  (146.83, 1.4), (0, 0.15), (110.00, 1.9), (0, 0.4),
                  (130.81, 1.6), (220.00, 2.2), (0, 0.4)]
    lead_final = gerar_melodia(tema_a + tema_b + tema_resolucao, 0.26, "senoide")
    baixo_final = gerar_melodia(baixo_tema, 0.20, "triangular")
    MUSICAS[99] = criar_som(mixar(lead_final, baixo_final, volume_total=0.7))


# ---------------------------------------------------------
# HUD / TELAS
# ---------------------------------------------------------
def desenhar_hud(canvas, gato, indice_fase):
    painel = pygame.Surface((230, 60), pygame.SRCALPHA)
    pygame.draw.rect(painel, HUD_FUNDO, painel.get_rect(), border_radius=14)
    canvas.blit(painel, (15, 15))

    for i in range(3):
        cor = LARANJA_GATO if i < gato.vidas else (90, 90, 90)
        pygame.draw.circle(canvas, cor, (40 + i * 28, 35), 10)
        pygame.draw.circle(canvas, PRETO, (40 + i * 28, 35), 10, 2)

    pygame.draw.circle(canvas, AMARELO_MOEDA, (40, 60), 8)
    pygame.draw.circle(canvas, AMARELO_MOEDA_ESCURO, (40, 60), 8, 2)
    texto = FONTE.render(f"x {gato.pontos}", True, BRANCO)
    canvas.blit(texto, (58, 50))

    if indice_fase < 5:
        fase_txt = FONTE_PEQUENA.render(f"FASE {indice_fase}/5 - {NOMES_FASE[indice_fase]}", True, BRANCO)
        canvas.blit(fase_txt, (LARGURA - fase_txt.get_width() - 12, 20))

    badge_x = LARGURA - 107
    if gato.tem_pulo_duplo:
        badge = pygame.Surface((92, 34), pygame.SRCALPHA)
        pygame.draw.rect(badge, (20, 30, 60, 160), badge.get_rect(), border_radius=12)
        canvas.blit(badge, (badge_x, 45))
        texto_badge = FONTE_PEQUENA.render("PULO 2X", True, (130, 210, 255))
        canvas.blit(texto_badge, (badge_x + 10, 56))
        badge_x -= 100

    if gato.turbo_timer > 0:
        badge = pygame.Surface((92, 34), pygame.SRCALPHA)
        pygame.draw.rect(badge, (15, 50, 35, 160), badge.get_rect(), border_radius=12)
        canvas.blit(badge, (badge_x, 45))
        segundos = gato.turbo_timer // 60 + 1
        texto_badge = FONTE_PEQUENA.render(f"TURBO {segundos}s", True, VERDE_SPEED)
        canvas.blit(texto_badge, (badge_x + 6, 56))

    versao = FONTE_PEQUENA.render(VERSAO_JOGO.split(" - ")[0], True, (255, 255, 255))
    canvas.blit(versao, (LARGURA - versao.get_width() - 8, ALTURA - 20))


def desenhar_titulo_evangelion(canvas, cx, cy, quadro):
    """Titulo em estilo inspirado em cards de titulo de anime tipo
    Evangelion: faixa diagonal escura com friso vermelho, tipografia
    grande em caixa alta e um leve tremor/pulso de energia."""
    linha1 = "A LENDA DO"
    linha2 = "GATO AVENTUREIRO"

    fonte1 = pygame.font.SysFont("Arial", 30, bold=True)
    fonte2 = pygame.font.SysFont("Arial", 50, bold=True)

    t1 = fonte1.render(linha1, True, BRANCO)
    t2 = fonte2.render(linha2, True, BRANCO)

    largura_faixa = max(t1.get_width(), t2.get_width()) + 70
    altura_faixa = t1.get_height() + t2.get_height() + 22

    faixa = pygame.Surface((largura_faixa, altura_faixa), pygame.SRCALPHA)
    pygame.draw.polygon(faixa, (8, 8, 10, 235), [
        (0, 10), (largura_faixa, 0), (largura_faixa, altura_faixa - 10), (0, altura_faixa)])
    pygame.draw.polygon(faixa, BRANCO, [
        (0, 10), (largura_faixa, 0), (largura_faixa, 4), (0, 14)])
    faixa_vermelha_y = altura_faixa * 0.46 + 3 * math.sin(quadro * 0.15)
    pygame.draw.line(faixa, VERMELHO, (0, faixa_vermelha_y), (largura_faixa, faixa_vermelha_y - 6), 5)

    canvas.blit(faixa, (cx - largura_faixa // 2, cy - altura_faixa // 2))
    canvas.blit(t1, (cx - t1.get_width() // 2, cy - altura_faixa // 2 + 8))
    canvas.blit(t2, (cx - t2.get_width() // 2, cy - altura_faixa // 2 + t1.get_height() + 12))


BOTOES_MENU_PRINCIPAL = {
    "jogar": pygame.Rect(LARGURA // 2 - 150, 265, 300, 55),
    "selecao": pygame.Rect(LARGURA // 2 - 150, 330, 300, 55),
    "creditos": pygame.Rect(LARGURA // 2 - 150, 395, 300, 55),
}
ROTULOS_MENU_PRINCIPAL = {
    "jogar": "JOGAR",
    "selecao": "SELECAO DE FASES",
    "creditos": "CREDITOS E AGRADECIMENTOS",
}

BOTAO_VOLTAR = pygame.Rect(20, 20, 110, 44)


def _desenhar_botao(canvas, rect, texto, fonte, cor_fundo, ativo=True):
    superficie = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    cor = cor_fundo if ativo else (50, 50, 50, 170)
    pygame.draw.rect(superficie, cor, superficie.get_rect(), border_radius=8)
    pygame.draw.rect(superficie, BRANCO if ativo else (110, 110, 110), superficie.get_rect(), 2, border_radius=8)
    canvas.blit(superficie, rect.topleft)
    cor_texto = BRANCO if ativo else (150, 150, 150)
    rotulo = fonte.render(texto, True, cor_texto)
    canvas.blit(rotulo, (rect.centerx - rotulo.get_width() // 2, rect.centery - rotulo.get_height() // 2))


def desenhar_menu_principal(canvas, quadro, gato_menu):
    desenhar_fundo(canvas, 0, 4, quadro)
    chao = pygame.Rect(-50, 400, LARGURA + 100, 60)
    desenhar_plataformas(canvas, 0, [chao], "rocha")
    gato_menu.desenhar(canvas, 0)

    desenhar_titulo_evangelion(canvas, LARGURA // 2, 108, quadro)

    _desenhar_botao(canvas, BOTOES_MENU_PRINCIPAL["jogar"], ROTULOS_MENU_PRINCIPAL["jogar"],
                     FONTE, (190, 30, 30, 210))
    _desenhar_botao(canvas, BOTOES_MENU_PRINCIPAL["selecao"], ROTULOS_MENU_PRINCIPAL["selecao"],
                     FONTE, (35, 35, 45, 210))
    _desenhar_botao(canvas, BOTOES_MENU_PRINCIPAL["creditos"], ROTULOS_MENU_PRINCIPAL["creditos"],
                     FONTE_PEQUENA, (35, 35, 45, 210))

    versao = FONTE_PEQUENA.render(VERSAO_JOGO.split(" - ")[0], True, BRANCO)
    canvas.blit(versao, (10, ALTURA - 20))


BOTOES_FASES = {}
_LARGURA_BOTAO_FASE = 130
_ESPACO_BOTAO_FASE = 20
_INICIO_X_FASES = LARGURA // 2 - (5 * _LARGURA_BOTAO_FASE + 4 * _ESPACO_BOTAO_FASE) // 2
for _i in range(1, 6):
    BOTOES_FASES[_i] = pygame.Rect(
        _INICIO_X_FASES + (_i - 1) * (_LARGURA_BOTAO_FASE + _ESPACO_BOTAO_FASE),
        200, _LARGURA_BOTAO_FASE, 110)


def desenhar_selecao_fases(canvas, quadro):
    canvas.fill((16, 16, 22))
    titulo = FONTE_GRANDE.render("SELECAO DE FASES", True, BRANCO)
    canvas.blit(titulo, (LARGURA // 2 - titulo.get_width() // 2, 90))

    for indice, rect in BOTOES_FASES.items():
        desbloqueada = indice in FASES_DESBLOQUEADAS
        cor_fundo = (60, 130, 210, 220) if desbloqueada else (45, 45, 50, 210)
        superficie = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(superficie, cor_fundo, superficie.get_rect(), border_radius=10)
        pygame.draw.rect(superficie, BRANCO if desbloqueada else (100, 100, 100),
                          superficie.get_rect(), 2, border_radius=10)
        canvas.blit(superficie, rect.topleft)

        numero = FONTE_MEDIA.render(str(indice), True, BRANCO if desbloqueada else (140, 140, 140))
        canvas.blit(numero, (rect.centerx - numero.get_width() // 2, rect.y + 8))

        nome = NOMES_FASE[indice] if desbloqueada else "?????"
        texto_nome = FONTE_PEQUENA.render(nome, True, BRANCO if desbloqueada else (150, 150, 150))
        canvas.blit(texto_nome, (rect.centerx - texto_nome.get_width() // 2, rect.y + 62))

        if not desbloqueada:
            cadeado = FONTE_MEDIA.render("X", True, (200, 60, 60))
            canvas.blit(cadeado, (rect.centerx - cadeado.get_width() // 2, rect.y + 30))

    dica = FONTE_PEQUENA.render("Fases bloqueadas se abrem ao concluir a fase anterior", True, (200, 200, 210))
    canvas.blit(dica, (LARGURA // 2 - dica.get_width() // 2, 330))

    _desenhar_botao(canvas, BOTAO_VOLTAR, "VOLTAR", FONTE_PEQUENA, (40, 40, 40, 210))


TEXTO_CREDITOS = [
    "GATO AVENTUREIRO",
    "",
    "Um jogo sobre Bergamota, o gato aventureiro,",
    "que se perdeu de casa e encarou 5 fases",
    "ate o covil do Tigre Gigante.",
    "",
    "--- EQUIPE ---",
    "",
    "Direcao Geral ................ Apollo",
    "Roteiro e Dialogos ........... Apollo",
    "Programacao .................. Apollo",
    "Design de Fases ............... Apollo",
    "Trilha Sonora Original ........ Apollo",
    "Efeitos Sonoros ............... Apollo",
    "Arte e Animacao do Gato ....... Apollo",
    "Fisica do Pulo Duplo (PhD) .... Apollo",
    "Controle de Qualidade ......... Apollo",
    "  (comeu pipoca testando)",
    "Cafe e Motivacao da Equipe .... Apollo",
    "Suporte Emocional do Tigre .... Apollo",
    "Estagiario que Ficou Ate Tarde  Apollo",
    "Relacoes Publicas com Peixes .. Apollo",
    "Consultoria de Lava (nao toque)  Apollo",
    "",
    "--- AGRADECIMENTOS ---",
    "",
    "Obrigado por jogar ate aqui!",
    "Cada fase, cada bloco quebrado,",
    "cada moeda coletada e ate as",
    "piadas nos cargos foram feitos",
    "com muito carinho, pensando em",
    "quem chegasse ate o final.",
    "",
    "Valeu por dar essa chance",
    "pro Gato Aventureiro.",
    "",
    "Ate a proxima aventura, Bergamota!",
    "",
    "",
]


def desenhar_creditos(canvas, quadro):
    canvas.fill((12, 12, 18))

    titulo = FONTE_GRANDE.render("CREDITOS", True, AMARELO_MOEDA)
    canvas.blit(titulo, (LARGURA // 2 - titulo.get_width() // 2, 20))

    # area onde o texto rola, para nao invadir o titulo nem o botao voltar
    area_texto = pygame.Rect(0, 85, LARGURA, ALTURA - 85)
    recorte_anterior = canvas.get_clip()
    canvas.set_clip(area_texto)

    altura_linha = 30
    altura_total = len(TEXTO_CREDITOS) * altura_linha
    velocidade_rolagem = 0.9  # pixels por quadro -- ajuste pra rolar mais rapido/devagar

    deslocamento = (quadro * velocidade_rolagem) % (altura_total + ALTURA)
    y_inicio = area_texto.bottom - deslocamento

    for i, linha in enumerate(TEXTO_CREDITOS):
        y = y_inicio + i * altura_linha
        if area_texto.top - altura_linha < y < area_texto.bottom:
            if linha == "":
                continue
            if linha.startswith("---"):
                texto = FONTE_MEDIA.render(linha, True, (255, 210, 130))
            else:
                texto = FONTE_PEQUENA.render(linha, True, BRANCO)
            canvas.blit(texto, (LARGURA // 2 - texto.get_width() // 2, y))

    canvas.set_clip(recorte_anterior)

    _desenhar_botao(canvas, BOTAO_VOLTAR, "VOLTAR", FONTE_PEQUENA, (40, 40, 40, 210))


def tela_transicao_fase(canvas, indice_fase, quadro_local):
    overlay = pygame.Surface((LARGURA, ALTURA), pygame.SRCALPHA)
    alpha = 220 if quadro_local < 30 else max(0, 220 - (quadro_local - 30) * 8)
    overlay.fill((10, 10, 20, alpha))
    canvas.blit(overlay, (0, 0))

    if indice_fase <= 5:
        titulo = f"FASE {indice_fase}" if indice_fase < 5 else "CHEFE FINAL"
        nome = NOMES_FASE[indice_fase]
        t1 = FONTE_GRANDE.render(titulo, True, (255, 220, 130))
        t2 = FONTE_MEDIA.render(nome, True, BRANCO)
        canvas.blit(t1, (LARGURA // 2 - t1.get_width() // 2, ALTURA // 2 - 50))
        canvas.blit(t2, (LARGURA // 2 - t2.get_width() // 2, ALTURA // 2 + 10))


def tela_mensagem(canvas, titulo, subtitulo, cor_titulo):
    overlay = pygame.Surface((LARGURA, ALTURA), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    canvas.blit(overlay, (0, 0))

    texto1 = FONTE_GRANDE.render(titulo, True, cor_titulo)
    canvas.blit(texto1, (LARGURA // 2 - texto1.get_width() // 2, ALTURA // 2 - 60))

    texto2 = FONTE.render(subtitulo, True, BRANCO)
    canvas.blit(texto2, (LARGURA // 2 - texto2.get_width() // 2, ALTURA // 2 + 10))

    texto3 = FONTE_PEQUENA.render("Toque na tela para jogar novamente", True, BRANCO)
    canvas.blit(texto3, (LARGURA // 2 - texto3.get_width() // 2, ALTURA // 2 + 55))


# ---------------------------------------------------------
# GERENCIADOR DE FASES / JOGO
# ---------------------------------------------------------
def montar_estado_fase(indice_fase, gato):
    if indice_fase == 5:
        dados = criar_fase_5()
        tigre = TigreGigante(1900, 300)
    else:
        dados = CRIADORES_DE_FASE[indice_fase]()
        tigre = None

    gato.modo = dados["modo_fisica"]
    gato.reposicionar(*dados["ponto_inicio"])

    return {
        "indice_fase": indice_fase,
        "dados": dados,
        "tigre": tigre,
        "camera_x": 0,
        "estado": "transicao",   # transicao | jogando | venceu_fase | perdeu | vitoria_final
        "quadro_local": 0,
    }


def novo_jogo():
    gato = Gato(60, 100)
    PARTICULAS.clear()
    FRAGMENTOS.clear()
    jogo = montar_estado_fase(1, gato)
    jogo["gato"] = gato
    tocar_musica_da_fase(1)
    return jogo


def avancar_para_fase(jogo, proximo_indice):
    gato = jogo["gato"]
    if proximo_indice != 5:
        # ao trocar de fase, os poderes coletados na fase anterior se
        # perdem -- exceto quando o gato esta indo para a fase final
        gato.tem_pulo_duplo = False
        gato.pulo_duplo_usado = False
        gato.turbo_timer = 0
    novo = montar_estado_fase(proximo_indice, gato)
    novo["gato"] = gato
    PARTICULAS.clear()
    FRAGMENTOS.clear()
    desbloquear_fase(proximo_indice)
    tocar_musica_da_fase(proximo_indice if proximo_indice != 5 else 5)
    return novo


def iniciar_fase_escolhida(indice_fase):
    """Comeca um jogo novo diretamente numa fase ja desbloqueada
    (usado no menu de selecao de fases)."""
    gato = Gato(60, 100)
    PARTICULAS.clear()
    FRAGMENTOS.clear()
    jogo = montar_estado_fase(indice_fase, gato)
    jogo["gato"] = gato
    tocar_musica_da_fase(indice_fase)
    return jogo


def atualizar_e_desenhar_fase_normal(jogo, teclas):
    gato = jogo["gato"]
    dados = jogo["dados"]

    for pm in dados["plataformas_moveis"]:
        pm.atualizar()

    plataformas_solidas = list(dados["plataformas"])
    deslocamentos = {}
    for pm in dados["plataformas_moveis"]:
        r = pm.rect()
        plataformas_solidas.append(r)
        deslocamentos[id(r)] = pm.deslocamento_x

    gato.atualizar(teclas, plataformas_solidas, CONTROLES, deslocamentos)

    # barreiras invisiveis: nao deixa o gato escapar da fase
    limite_direita = dados["fim_fase_x"] + 80
    gato.x = max(0, min(gato.x, limite_direita))

    atualizar_blocos(dados["blocos"], gato, dados["moedas"],
                      [dados["cor_bloco"], dados["cor_bloco_escuro"]])
    atualizar_moedas(dados["moedas"], gato)
    atualizar_inimigos(dados["inimigos"], gato, dados["ponto_inicio"])
    atualizar_powerups(dados["powerups"], gato)
    checar_perigos(dados["perigos"], gato, dados["ponto_inicio"])
    atualizar_particulas()
    atualizar_fragmentos(plataformas_solidas)

    alvo_camera = gato.x - LARGURA // 3
    jogo["camera_x"] += (alvo_camera - jogo["camera_x"]) * 0.15
    jogo["camera_x"] = max(0, min(jogo["camera_x"], dados["fim_fase_x"] - LARGURA + 100))

    if dados["bandeira"] is not None and gato.rect().colliderect(dados["bandeira"]):
        jogo["estado"] = "venceu_fase"
        jogo["quadro_local"] = 0
        tocar("fase_completa")
    elif gato.vidas <= 0:
        jogo["estado"] = "perdeu"
        jogo["quadro_local"] = 0
        tocar("perder_jogo")


def desenhar_fase_normal(canvas, jogo, quadro):
    gato = jogo["gato"]
    dados = jogo["dados"]
    cam = jogo["camera_x"]

    desenhar_fundo(canvas, cam, jogo["indice_fase"], quadro)
    desenhar_plataformas(canvas, cam, dados["plataformas"], dados["estilo"])
    for pm in dados["plataformas_moveis"]:
        pm.desenhar(canvas, cam)
    desenhar_blocos(canvas, cam, dados["blocos"], dados["cor_bloco"], dados["cor_bloco_escuro"])
    desenhar_perigos(canvas, cam, dados["perigos"], dados["perigo_estilo"])
    desenhar_moedas(canvas, cam, dados["moedas"], quadro)
    desenhar_powerups(canvas, cam, dados["powerups"], quadro)
    desenhar_inimigos(canvas, cam, dados["inimigos"])
    if dados["bandeira"] is not None:
        desenhar_bandeira(canvas, cam, dados["bandeira"])
    desenhar_fragmentos(canvas, cam)
    desenhar_particulas(canvas, cam)
    gato.desenhar(canvas, cam)
    desenhar_hud(canvas, gato, jogo["indice_fase"])


# ---------------------------------------------------------
# FASE 5 - LOGICA DO CHEFE (TIGRE GIGANTE)
# ---------------------------------------------------------
def atualizar_e_desenhar_fase_chefe(jogo, teclas):
    gato = jogo["gato"]
    dados = jogo["dados"]
    tigre = jogo["tigre"]

    plataformas_solidas = list(dados["plataformas"])
    gato.atualizar(teclas, plataformas_solidas, CONTROLES)
    gato.x = max(0, min(gato.x, dados["fim_fase_x"]))

    tigre.atualizar(gato)
    atualizar_particulas()
    atualizar_fragmentos(plataformas_solidas)

    alvo_camera = gato.x - LARGURA // 3
    jogo["camera_x"] += (alvo_camera - jogo["camera_x"]) * 0.15
    jogo["camera_x"] = max(0, min(jogo["camera_x"], dados["fim_fase_x"] - LARGURA + 100))

    if tigre.derrotado:
        jogo["estado"] = "vitoria_final"
        jogo["quadro_local"] = 0
        parar_musica()
        tocar_musica_da_fase(99)
    elif gato.vidas <= 0:
        jogo["estado"] = "perdeu"
        jogo["quadro_local"] = 0
        tocar("perder_jogo")


def desenhar_fase_chefe(canvas, jogo, quadro):
    gato = jogo["gato"]
    dados = jogo["dados"]
    tigre = jogo["tigre"]
    cam = jogo["camera_x"]

    desenhar_fundo(canvas, cam, 5, quadro)
    desenhar_plataformas(canvas, cam, dados["plataformas"], dados["estilo"])
    desenhar_fragmentos(canvas, cam)
    desenhar_particulas(canvas, cam)
    tigre.desenhar(canvas, cam, quadro)
    gato.desenhar(canvas, cam)
    desenhar_hud(canvas, gato, 5)
    tigre.desenhar_barra_vida(canvas)


# ---------------------------------------------------------
# CONTROLE DE FASES DESBLOQUEADAS
# ---------------------------------------------------------
FASES_DESBLOQUEADAS = {1}


def desbloquear_fase(indice_fase):
    FASES_DESBLOQUEADAS.add(indice_fase)


# ---------------------------------------------------------
# MUSICA / PAUSA
# ---------------------------------------------------------
MUSICA_ATIVADA = True
INDICE_MUSICA_ATUAL = None


def tocar_musica_da_fase(indice_fase):
    global CANAL_MUSICA, INDICE_MUSICA_ATUAL
    INDICE_MUSICA_ATUAL = indice_fase
    if not SOM_ATIVADO:
        return
    if CANAL_MUSICA is not None:
        CANAL_MUSICA.stop()
        CANAL_MUSICA = None
    musica = MUSICAS.get(indice_fase)
    if musica is None:
        return
    CANAL_MUSICA = musica
    if MUSICA_ATIVADA:
        musica.play(loops=-1)


def alternar_musica():
    global MUSICA_ATIVADA, CANAL_MUSICA
    MUSICA_ATIVADA = not MUSICA_ATIVADA
    if not MUSICA_ATIVADA:
        if CANAL_MUSICA is not None:
            CANAL_MUSICA.stop()
    else:
        if INDICE_MUSICA_ATUAL is not None:
            tocar_musica_da_fase(INDICE_MUSICA_ATUAL)


BOTAO_PAUSA = pygame.Rect(LARGURA // 2 - 22, 15, 44, 44)
BOTAO_CONTINUAR = pygame.Rect(LARGURA // 2 - 110, 140, 220, 50)
BOTAO_MUSICA = pygame.Rect(LARGURA // 2 - 30, 215, 60, 60)
BOTAO_MENU_PRINCIPAL_PAUSA = pygame.Rect(LARGURA // 2 - 110, 320, 220, 50)
BOTAO_CONFIRMA_SIM = pygame.Rect(LARGURA // 2 - 110, 260, 100, 50)
BOTAO_CONFIRMA_NAO = pygame.Rect(LARGURA // 2 + 10, 260, 100, 50)


def desenhar_botao_pausa(canvas):
    superficie = pygame.Surface((BOTAO_PAUSA.width, BOTAO_PAUSA.height), pygame.SRCALPHA)
    pygame.draw.rect(superficie, (30, 30, 40, 160), superficie.get_rect(), border_radius=10)
    pygame.draw.rect(superficie, BRANCO, superficie.get_rect(), 2, border_radius=10)
    canvas.blit(superficie, BOTAO_PAUSA.topleft)
    cx, cy = BOTAO_PAUSA.center
    pygame.draw.rect(canvas, BRANCO, (cx - 8, cy - 10, 6, 20))
    pygame.draw.rect(canvas, BRANCO, (cx + 2, cy - 10, 6, 20))


def desenhar_icone_musica(canvas, rect, ativada):
    centro = rect.center
    pygame.draw.circle(canvas, (45, 45, 60), centro, rect.width // 2)
    pygame.draw.circle(canvas, BRANCO, centro, rect.width // 2, 2)

    nx, ny = centro[0] - 10, centro[1] + 8
    pygame.draw.circle(canvas, BRANCO, (nx, ny), 5)
    pygame.draw.circle(canvas, BRANCO, (nx + 16, ny - 3), 5)
    pygame.draw.line(canvas, BRANCO, (nx + 5, ny), (nx + 5, ny - 22), 3)
    pygame.draw.line(canvas, BRANCO, (nx + 21, ny - 3), (nx + 21, ny - 25), 3)
    pygame.draw.line(canvas, BRANCO, (nx + 5, ny - 22), (nx + 21, ny - 25), 3)

    if not ativada:
        pygame.draw.line(canvas, VERMELHO, (rect.left + 3, rect.top + 3),
                          (rect.right - 3, rect.bottom - 3), 6)


def desenhar_menu_pausa(canvas):
    overlay = pygame.Surface((LARGURA, ALTURA), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    canvas.blit(overlay, (0, 0))

    titulo = FONTE_GRANDE.render("PAUSADO", True, BRANCO)
    canvas.blit(titulo, (LARGURA // 2 - titulo.get_width() // 2, 65))

    _desenhar_botao(canvas, BOTAO_CONTINUAR, "CONTINUAR", FONTE, (40, 120, 60, 230))

    desenhar_icone_musica(canvas, BOTAO_MUSICA, MUSICA_ATIVADA)
    rotulo = "MUSICA LIGADA" if MUSICA_ATIVADA else "SEM MUSICA"
    texto_rotulo = FONTE_PEQUENA.render(rotulo, True, BRANCO)
    canvas.blit(texto_rotulo, (LARGURA // 2 - texto_rotulo.get_width() // 2, BOTAO_MUSICA.bottom + 6))

    _desenhar_botao(canvas, BOTAO_MENU_PRINCIPAL_PAUSA, "MENU PRINCIPAL", FONTE_PEQUENA, (120, 40, 40, 230))


def desenhar_popup_confirmacao(canvas):
    overlay = pygame.Surface((LARGURA, ALTURA), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 130))
    canvas.blit(overlay, (0, 0))

    caixa = pygame.Rect(LARGURA // 2 - 160, 150, 320, 160)
    superficie = pygame.Surface((caixa.width, caixa.height), pygame.SRCALPHA)
    pygame.draw.rect(superficie, (30, 30, 40, 245), superficie.get_rect(), border_radius=14)
    pygame.draw.rect(superficie, BRANCO, superficie.get_rect(), 2, border_radius=14)
    canvas.blit(superficie, caixa.topleft)

    texto = FONTE_MEDIA.render("TEM CERTEZA?", True, BRANCO)
    canvas.blit(texto, (LARGURA // 2 - texto.get_width() // 2, caixa.y + 20))
    sub = FONTE_PEQUENA.render("Voce vai perder o progresso da fase", True, (200, 200, 210))
    canvas.blit(sub, (LARGURA // 2 - sub.get_width() // 2, caixa.y + 60))

    _desenhar_botao(canvas, BOTAO_CONFIRMA_SIM, "SIM", FONTE, (150, 40, 40, 235))
    _desenhar_botao(canvas, BOTAO_CONFIRMA_NAO, "NAO", FONTE, (40, 120, 60, 235))


def desenhar_tela_morte(canvas, jogo, quadro):
    q = jogo["quadro_local"]

    # brasas subindo, igual a fase do vulcao
    if q % 3 == 0:
        espalhar_particulas(jogo["camera_x"] + random.uniform(0, LARGURA), ALTURA,
                             (255, 140, 40), 2, gravidade=-0.18)
    if q % 5 == 0:
        espalhar_particulas(jogo["camera_x"] + random.uniform(0, LARGURA), ALTURA,
                             (255, 60, 30), 1, gravidade=-0.1)
    desenhar_particulas(canvas, jogo["camera_x"])

    alpha = min(190, q * 5)
    overlay = pygame.Surface((LARGURA, ALTURA), pygame.SRCALPHA)
    overlay.fill((90, 0, 0, alpha))
    canvas.blit(overlay, (0, 0))

    if q > 15:
        texto1 = FONTE_GRANDE.render("VOCE MORREU", True, VERMELHO)
        canvas.blit(texto1, (LARGURA // 2 - texto1.get_width() // 2, ALTURA // 2 - 60))
        texto2 = FONTE.render(f"Pontos: {jogo['gato'].pontos}", True, BRANCO)
        canvas.blit(texto2, (LARGURA // 2 - texto2.get_width() // 2, ALTURA // 2 + 5))
    if q > 50:
        texto3 = FONTE_PEQUENA.render("Voltando ao menu...", True, (220, 220, 220))
        canvas.blit(texto3, (LARGURA // 2 - texto3.get_width() // 2, ALTURA // 2 + 50))


# ---------------------------------------------------------
# LOOP PRINCIPAL (obrigatorio p/ Pydroid 3 e p/ pygbag no navegador)
# ---------------------------------------------------------
async def main():
    carregar_audio()

    estado_app = "menu"   # menu | selecao | creditos | jogo
    jogo = None
    quadro = 0
    gato_menu = Gato(LARGURA // 2 - 20, 340)

    rodando = True
    while rodando:
        toque_usado_neste_quadro = False
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                rodando = False

            CONTROLES.processar_evento(evento)
            pos_toque = obter_posicao_toque(evento)
            if pos_toque is not None:
                # no touchscreen (Android/SDL), um mesmo toque costuma gerar
                # DOIS eventos (FINGERDOWN + um MOUSEBUTTONDOWN sintetico).
                # Sem esse controle, cada toque era processado duas vezes no
                # mesmo quadro -- por isso "MENU PRINCIPAL" no pause virava
                # "JOGAR" de novo (o botao SIM do popup fica bem em cima do
                # botao JOGAR do menu) e o botao de musica ligava/desligava
                # em sequencia, parecendo que a musica so reiniciava.
                if toque_usado_neste_quadro:
                    pos_toque = None
                else:
                    toque_usado_neste_quadro = True

            if estado_app == "menu":
                if pos_toque is not None:
                    if BOTOES_MENU_PRINCIPAL["jogar"].collidepoint(pos_toque):
                        jogo = novo_jogo()
                        estado_app = "jogo"
                    elif BOTOES_MENU_PRINCIPAL["selecao"].collidepoint(pos_toque):
                        estado_app = "selecao"
                    elif BOTOES_MENU_PRINCIPAL["creditos"].collidepoint(pos_toque):
                        estado_app = "creditos"

            elif estado_app == "selecao":
                if pos_toque is not None:
                    if BOTAO_VOLTAR.collidepoint(pos_toque):
                        estado_app = "menu"
                    else:
                        for indice, rect in BOTOES_FASES.items():
                            if indice in FASES_DESBLOQUEADAS and rect.collidepoint(pos_toque):
                                jogo = iniciar_fase_escolhida(indice)
                                estado_app = "jogo"

            elif estado_app == "creditos":
                if pos_toque is not None and BOTAO_VOLTAR.collidepoint(pos_toque):
                    estado_app = "menu"

            elif estado_app == "jogo":
                confirmando = jogo.get("confirmando_saida", False)
                pausado = jogo.get("pausado", False)

                if jogo["estado"] == "jogando" and pos_toque is not None:
                    if confirmando:
                        if BOTAO_CONFIRMA_SIM.collidepoint(pos_toque):
                            parar_musica()
                            jogo["pausado"] = False
                            jogo["confirmando_saida"] = False
                            estado_app = "menu"
                        elif BOTAO_CONFIRMA_NAO.collidepoint(pos_toque):
                            jogo["confirmando_saida"] = False
                    elif pausado:
                        if BOTAO_CONTINUAR.collidepoint(pos_toque):
                            jogo["pausado"] = False
                        elif BOTAO_MUSICA.collidepoint(pos_toque):
                            alternar_musica()
                        elif BOTAO_MENU_PRINCIPAL_PAUSA.collidepoint(pos_toque):
                            jogo["confirmando_saida"] = True
                    else:
                        if BOTAO_PAUSA.collidepoint(pos_toque):
                            jogo["pausado"] = True

                elif jogo["estado"] in ("perdeu", "vitoria_final") and pos_toque is not None:
                    if jogo["estado"] == "vitoria_final":
                        parar_musica()
                        estado_app = "menu"
                    # em "perdeu" nao faz nada no toque -- ele volta sozinho pro menu

        teclas = pygame.key.get_pressed()

        if estado_app == "menu":
            gato_menu.andando += 1
            desenhar_menu_principal(CANVAS, quadro, gato_menu)

        elif estado_app == "selecao":
            desenhar_selecao_fases(CANVAS, quadro)

        elif estado_app == "creditos":
            desenhar_creditos(CANVAS, quadro)

        elif estado_app == "jogo":
            eh_chefe = jogo["indice_fase"] == 5
            pausado = jogo.get("pausado", False)
            confirmando = jogo.get("confirmando_saida", False)

            if jogo["estado"] == "transicao":
                jogo["quadro_local"] += 1
                if eh_chefe:
                    desenhar_fase_chefe(CANVAS, jogo, quadro)
                else:
                    desenhar_fase_normal(CANVAS, jogo, quadro)
                tela_transicao_fase(CANVAS, jogo["indice_fase"], jogo["quadro_local"])
                if jogo["quadro_local"] > 70:
                    jogo["estado"] = "jogando"

            elif jogo["estado"] == "jogando":
                if not pausado and not confirmando:
                    if eh_chefe:
                        atualizar_e_desenhar_fase_chefe(jogo, teclas)
                        desenhar_fase_chefe(CANVAS, jogo, quadro)
                    else:
                        atualizar_e_desenhar_fase_normal(jogo, teclas)
                        desenhar_fase_normal(CANVAS, jogo, quadro)
                    CONTROLES.desenhar(CANVAS)
                    desenhar_botao_pausa(CANVAS)
                else:
                    # jogo congelado: so redesenha o ultimo quadro, sem atualizar fisica
                    if eh_chefe:
                        desenhar_fase_chefe(CANVAS, jogo, quadro)
                    else:
                        desenhar_fase_normal(CANVAS, jogo, quadro)
                    if confirmando:
                        desenhar_menu_pausa(CANVAS)
                        desenhar_popup_confirmacao(CANVAS)
                    else:
                        desenhar_menu_pausa(CANVAS)

            elif jogo["estado"] == "venceu_fase":
                desenhar_fase_normal(CANVAS, jogo, quadro)
                jogo = avancar_para_fase(jogo, jogo["indice_fase"] + 1)
                jogo["estado"] = "transicao"

            elif jogo["estado"] == "perdeu":
                if eh_chefe:
                    desenhar_fase_chefe(CANVAS, jogo, quadro)
                else:
                    desenhar_fase_normal(CANVAS, jogo, quadro)
                desenhar_tela_morte(CANVAS, jogo, quadro)
                jogo["quadro_local"] += 1
                if jogo["quadro_local"] > 130:
                    parar_musica()
                    estado_app = "menu"

            elif jogo["estado"] == "vitoria_final":
                desenhar_fase_chefe(CANVAS, jogo, quadro)
                tela_mensagem(CANVAS, "VOCE VENCEU!", f"Pontos: {jogo['gato'].pontos}", AMARELO_MOEDA)

        atualizar_tela_real()
        quadro += 1
        RELOGIO.tick(FPS)
        await asyncio.sleep(0)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    asyncio.run(main())
