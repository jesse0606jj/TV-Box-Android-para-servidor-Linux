# Instalando Armbian em TV Box RK3228A/RK3229 via SSH e dd

Guia completo e documentado de como instalar o Armbian em um TV Box com chip RK322x sem ferramentas de rede disponíveis no Multitool (sem wget, curl, nc ou sftp).

**Hardware usado:** TV Box MXQ Pro 4K com chip RK3228A  
**Sistema instalado:** Armbian 22.02.0 Bullseye com kernel 4.4.194  
**Resultado:** https://tvbox.jessereis.com.br

---

## Índice

1. [O que você vai precisar](#1-o-que-você-vai-precisar)
2. [Gravar o Multitool no cartão SD](#2-gravar-o-multitool-no-cartão-sd)
3. [Expandir a partição MULTITOOL](#3-expandir-a-partição-multitool)
4. [Bootar o Multitool no TV Box](#4-bootar-o-multitool-no-tv-box)
5. [Conectar via SSH](#5-conectar-via-ssh)
6. [Transferir a imagem via servidor HTTP](#6-transferir-a-imagem-via-servidor-http)
7. [Gravar a imagem na eMMC via dd](#7-gravar-a-imagem-na-emmc-via-dd)
8. [Configurar o Armbian](#8-configurar-o-armbian)
9. [Solução de problemas](#9-solução-de-problemas)

---

## 1. O que você vai precisar

- TV Box com chip RK3228A, RK3228B ou RK3229
- Cartão microSD de 16 GB ou mais
- Cabo de rede (ethernet)
- PC com Windows
- Balena Etcher: https://www.balena.io/etcher
- MiniTool Partition Wizard Free: https://www.partitionwizard.com
- Multitool para RK322x: https://www.mediafire.com/file/2wzb3y4er4zdmld/multitool.img/file
- Imagem do Armbian para rk322x-box: https://github.com/armbian/community/releases

---

## 2. Gravar o Multitool no cartão SD

Abra o Balena Etcher, selecione o arquivo `multitool.img.xz` e grave no cartão microSD. Após gravar, o cartão terá duas partições visíveis no Windows:

- **BOOTSTRAP (D:)** — 64 MB — partição de boot, não mexa
- **MULTITOOL (E:)** — ~378 MB — partição de trabalho

O restante do espaço fica não alocado e invisível para o Windows.

---

## 3. Expandir a partição MULTITOOL

A partição MULTITOOL original tem apenas ~378 MB, insuficiente para armazenar a imagem do Armbian. É necessário expandi-la para usar o espaço livre do cartão.

Abra o MiniTool Partition Wizard, localize o cartão SD na lista de discos, clique com botão direito na partição MULTITOOL e selecione Estender. Arraste o slider para ocupar todo o espaço disponível e clique em Aplicar.

> Atenção: não abra o cartão SD no Windows Explorer após a expansão. Ferramentas como "Verificar e Corrigir" podem corromper a partição NTFS do Multitool.

---

## 4. Bootar o Multitool no TV Box

Insira o cartão SD no TV Box com ele desligado. Ligue o TV Box — após alguns segundos o LED azul começa a piscar e o menu do Multitool aparece na tela.

Se o menu não aparecer e o Android iniciar normalmente, procure um buraco pequeno no TV Box chamado AV reset ou recovery e pressione com um clipe enquanto liga.

O menu do Multitool oferece as seguintes opções:

```
1 - Backup flash
2 - Restore flash
3 - Erase flash
4 - Drop to Bash shell
5 - Burn image to flash
8 - Reboot
9 - Shutdown
```

---

## 5. Conectar via SSH

Conecte o TV Box ao roteador via cabo ethernet. No menu do Multitool, selecione a opção **4 — Drop to Bash shell**.

Para obter o IP do TV Box, execute no terminal:

```bash
ip addr
```

Se o IP não aparecer (apenas 169.254.x.x), force a obtenção via DHCP:

```bash
dhclient eth0
ip addr
```

O IP será exibido na interface eth0, no formato 192.168.x.x.

No PC com Windows, abra o CMD ou PowerShell e conecte:

```bash
ssh root@192.168.x.x
```

Não há senha por padrão. Ao conectar, você verá:

```
Welcome to Multitool SSH session!
```

---

## 6. Transferir a imagem via servidor HTTP

O Multitool não possui wget, curl, nc, sftp ou python. A solução é criar um servidor HTTP no PC com Windows e usar o bash do Multitool para baixar via `/dev/tcp`.

### No PC Windows, abra o PowerShell na pasta com a imagem do Armbian:

```powershell
cd "C:\Users\SeuUsuario\Downloads"
python -m http.server 9876
```

O servidor ficará aguardando em `http://0.0.0.0:9876`.

> Se a porta 9876 der erro de permissão, tente outra porta alta como 8765 ou 7654.

### No SSH do TV Box, inspecione o cabeçalho HTTP:

```bash
exec 3<>/dev/tcp/192.168.x.x/9876
printf "GET /nome-da-imagem.img HTTP/1.0\r\nHost: 192.168.x.x\r\nConnection: close\r\n\r\n" >&3
head -c 500 <&3 | od -A d -c | head -20
```

O `od -A d -c` exibe o dump em decimal. Procure a sequência `\r \n \r \n` (fim do cabeçalho HTTP). O número na coluna da esquerda logo após essa sequência é o offset em bytes — geralmente entre 150 e 300 bytes.

---

## 7. Gravar a imagem na eMMC via dd

Com o offset do cabeçalho identificado (no exemplo abaixo, 208 bytes), execute o stream direto para a eMMC:

```bash
exec 3<>/dev/tcp/192.168.x.x/9876
printf "GET /nome-da-imagem.img HTTP/1.0\r\nHost: 192.168.x.x\r\nConnection: close\r\n\r\n" >&3
{ dd bs=208 count=1 > /dev/null; dd bs=4M of=/dev/mmcblk2; } <&3
sync
```

O primeiro `dd` descarta os 208 bytes do cabeçalho HTTP. O segundo grava o restante direto na eMMC (`/dev/mmcblk2`). O `sync` garante que todos os dados foram escritos antes de desligar.

Aguarde a conclusão. A velocidade típica é de ~10 MB/s. Uma imagem de 768 MB leva cerca de 80 segundos.

Exemplo de saída ao concluir:

```
1+0 records in
1+0 records out
208 bytes copied, 0.000567 s, 367 kB/s
0+65693 records in
0+65693 records out
767557632 bytes (768 MB, 732 MiB) copied, 78.2104 s, 9.8 MB/s
```

> **Atenção:** Verifique os dispositivos antes de executar. No Multitool, a eMMC geralmente é `/dev/mmcblk2` e o cartão SD é `/dev/mmcblk0`. Confirme com `lsblk` antes de gravar.

Após concluir, pressione `Ctrl+D` para sair do bash e voltar ao menu do Multitool. Selecione **9 Shutdown**, remova o cartão SD e ligue o TV Box.

---

## 8. Configurar o Armbian

No primeiro boot, o sistema pedirá para criar a senha do root. A senha deve ter no mínimo 8 caracteres. Depois crie um usuário comum.

Após logar, execute o utilitário de configuração do hardware:

```bash
rk322x-config
```

Configure as opções na seguinte ordem:

**SoC:** Selecione de acordo com seu chip. Use RK3229 (max 1.4GHz) para chips RK3229, ou a opção correspondente para RK3228A/B.

**Memória interna:** Selecione eMMC flash memory.

**Otimizações eMMC:** Selecione apenas emmc-pins. Deixe as demais desmarcadas.

**Velocidade da RAM:** Selecione ddr3-800 para melhor desempenho. Se o sistema ficar instável, volte e use default.

**Configuração de LED:** Selecione led-conf2 (R329q, MXQ-RK3229) para TV Boxes da linha MXQ.

**Módulo Wi-Fi:** O sistema detecta automaticamente. Para chips South Silicon Valley 6051p/6256p, selecione ssv6051. Se o Wi-Fi não funcionar após reiniciar, tente ssv6x5x.

Reinicie para aplicar:

```bash
reboot
```

---

## 9. Solução de problemas

**O Multitool não boota pelo cartão SD**
Pressione o botão de reset AV com um clipe enquanto liga o TV Box.

**Erro "There has been an error mounting the MULTITOOL partition"**
A partição MULTITOOL ficou corrompida após a expansão no Windows. O menu do Multitool ainda funciona normalmente. Use o método de transferência via SSH descrito neste guia.

**IP 169.254.x.x na interface eth0**
O TV Box não recebeu IP via DHCP. Verifique o cabo de rede e execute `dhclient eth0`.

**Erro "Target filesystem doesn't have requested /sbin/init"**
O cabeçalho HTTP foi gravado junto com a imagem. Regravar com o offset correto resolve o problema.

**Wi-Fi não funciona após configuração**
Execute novamente `rk322x-config` e tente o outro driver de Wi-Fi disponível.

---

## Referências

- Fórum oficial Armbian RK322x: https://forum.armbian.com/topic/34923-csc-armbian-for-rk322x-tv-box-boards
- Repositório Armbian Community: https://github.com/armbian/community/releases
- Guia de instalação MXQ Pro: https://github.com/gridiii/mxq-4k-pro-rk322x-armbian-install

---

Resultado final: https://tvbox.jessereis.com.br
