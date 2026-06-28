> **PT-BR:** Guia rápido para executar e validar o SonarQube localmente antes de abrir um PR.
>
> **EN:** Quick guide to run and validate SonarQube locally before opening a PR.

---

## PT-BR

### Pré-requisitos

- SonarQube 10.6+ rodando em `http://127.0.0.1:9000` ou IP acessível pelo runner
- Token de usuário com permissão `Execute Analysis`
- Java 17 e `curl`

### Passos

1. **Suba o Sonar local:** `docker compose up -d sonarqube`
2. **Exportar variáveis:**
   ```bash
   export SONAR_HOST_URL=http://127.0.0.1:9000
   export SONAR_TOKEN=<token>
   ```
3. **Executar o scanner:**
   ```bash
   ./scripts/seed-render-queue.sh --check-sonar
   # ou manualmente
   sonar-scanner \
     -Dsonar.host.url="$SONAR_HOST_URL" \
     -Dsonar.login="$SONAR_TOKEN"
   ```
4. **Verificar o job `SonarQube Scan` no GitHub Actions** (ainda em PR) para garantir que a etapa consegue baixar o scanner pela URL principal ou pelo mirror do GitHub quando houver HTTP 403.

### Troubleshooting

| Sintoma | Ação |
| --- | --- |
| `curl: (22) ... 403` | Verifique se o runner tem acesso à CDN da SonarSource; o workflow já faz fallback para o mirror GitHub. |
| `Failed to connect to 127.0.0.1:9000` | Certifique-se de expor o Sonar via `localhost` ou ajuste `SONAR_HOST_URL` para o IP do host/WSL. |

---

## EN

### Requirements

- SonarQube 10.6+ reachable at `http://127.0.0.1:9000`
- User token with `Execute Analysis`
- Java 17 + `curl`

### Steps

1. **Start Sonar locally:** `docker compose up -d sonarqube`
2. **Export env vars:**
   ```bash
   export SONAR_HOST_URL=http://127.0.0.1:9000
   export SONAR_TOKEN=<token>
   ```
3. **Run scanner:** see example above (same command).
4. **Check the CI job** to ensure the download + analysis succeeds before merging.

### Notes

- The CI uses a fallback URL (`github.com/SonarSource/...`) when the primary CDN rate-limits the runner.
- Keep the secrets `SONAR_HOST_URL`/`SONAR_TOKEN` updated in the repository settings.
