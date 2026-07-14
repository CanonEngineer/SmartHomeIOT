# Metodologia Experimental

## Perguntas de pesquisa suportadas pela bancada

1. Qual a latência ponta a ponta do caminho de atuação (API → estado → UI/atuador)?
2. Qual o desalinhamento temporal (skew) entre heartbeats Arduino e Raspberry?
3. Como o Sync Quality Index (SQI) responde a injeção de falha/atraso?
4. A máquina de estados dos atuadores permanece consistente em cenários compostos?

## Protocolo de ensaio

1. Subir o servidor em modo simulação (`python app.py`)
2. Abrir o Research Lab em http://127.0.0.1:8000
3. Executar um experimento do catálogo
4. Exportar CSV/JSON em `experiments/exports/`
5. Registrar hipótese, parâmetros e SQI no caderno de tese

## Catálogo de experimentos

| ID | Hipótese operacional |
|----|----------------------|
| `sync_latency` | Skew Arduino↔Raspberry permanece baixo em regime estável |
| `actuator_response` | Mediana de latência de comando < limiar definido |
| `fault_injection` | SQI cai sob atraso artificial e recupera |
| `end_to_end` | Sequência welcome→garage→night mantém consistência de estado |

## Variáveis

- **Independentes:** ciclos, delay artificial, cenário
- **Dependentes:** latência (p50/p95), skew, SQI, consistência de atuadores
- **Controle:** modo simulação vs hardware real + MQTT

## Reprodutibilidade

- Protocolo versionado (`PROTOCOL_VERSION`)
- Export JSON com metadados + amostras
- Export CSV tabular para estatística (R/Python/Excel)
- Endpoint `/api/research/thesis-brief.md` para slides

## Ameaça à validade

- Simulação não captura jitter RF/Wi-Fi real → validar com hardware
- Relógio não é NTP-sincronizado entre placas físicas → usar timestamps do edge
- Carga do host afeta latência de software → reportar máquina e carga

## Entregáveis sugeridos para a tese

- Diagrama de camadas L1–L5
- Tabela de métricas (antes/depois de fault injection)
- Gráfico de latência do Research Lab
- Discussão do SQI como indicador composto
