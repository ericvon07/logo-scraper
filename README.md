# logo-scraper

Fetches and downloads company logos from multiple sources — logo.dev API, company websites, and LinkedIn — with automatic priority-based fallback.

## Features

- **logo.dev** — high-quality logos via REST API (fastest, most reliable)
- **Website scraping** — extracts favicons, Open Graph images, Twitter cards, and `<img>` tags from the company's own site
- **LinkedIn** — last-resort fallback using public company page HTML (og:image, JSON-LD, img tags)

## Installation

```bash
git clone https://github.com/your-username/logo-scraper.git
cd logo-scraper
pip install -e .
```

**Set up your logo.dev API key:**

```bash
cp .env.example .env
# Edit .env and add your key:
# LOGODEV_API_KEY=your_key_here
```

Get a free API key at [logo.dev](https://www.logo.dev).

## Usage

### Single company

```bash
# Minimal — only name (logo.dev will try company.com)
logo-scraper --name "Stripe"

# With website URL (improves logo.dev domain resolution + enables website scraping)
logo-scraper --name "Nubank" --url "https://nubank.com.br"

# With all three sources available
logo-scraper --name "Spotify" \
             --url "https://spotify.com" \
             --linkedin "https://www.linkedin.com/company/spotify"

# Custom output directory
logo-scraper --name "Vercel" --url "https://vercel.com" --output "./logos/vercel"

# Pass API key directly (overrides .env)
logo-scraper --name "Stripe" --logodev-api-key "pk_YOUR_KEY"
```

### Batch mode

```bash
# Process multiple companies from a JSON file
logo-scraper --from-file examples/companies.json --output "./output"
```

The JSON file must be a list of objects with a `name` field. `url` and `linkedin` are optional:

```json
[
  { "name": "Nubank",  "url": "https://nubank.com.br",  "linkedin": "https://www.linkedin.com/company/nubank" },
  { "name": "Stripe",  "url": "https://stripe.com" },
  { "name": "iFood",                                    "linkedin": "https://www.linkedin.com/company/ifood-" }
]
```

Batch output is organized per company (`./output/nubank/`, `./output/stripe/`, …) and ends with a summary table:

```
+------------------+-------+----------+
| Company          | Logos | Sources  |
+------------------+-------+----------+
| Nubank           | 1     | logodev  |
| Stripe           | 1     | logodev  |
| iFood            | 1     | linkedin |
+------------------+-------+----------+

3/3 companies with logos found  |  3 logo(s) total
```

## Running tests

```bash
pytest
```

## Known limitations

- **LinkedIn blocks scraping aggressively** — expect 403s, redirects to login, or status 999. Success rate varies and can drop to near zero without warning.
- **Website scraping is heuristic** — pages that load images via JavaScript won't work (no headless browser).
- **logo.dev has rate limits** on the free tier.

## License

MIT — see [LICENSE](LICENSE) for details.

---

# logo-scraper (PT)

Busca e baixa logos de empresas de múltiplas fontes — API do logo.dev, sites das empresas e LinkedIn — com fallback automático por prioridade.

## Funcionalidades

- **logo.dev** — logos de alta qualidade via REST API (mais rápido e confiável)
- **Scraping do site** — extrai favicons, Open Graph images, Twitter cards e tags `<img>` do site da empresa
- **LinkedIn** — fallback de último recurso usando o HTML público da página da empresa (og:image, JSON-LD, img tags)

## Instalação

```bash
git clone https://github.com/your-username/logo-scraper.git
cd logo-scraper
pip install -e .
```

**Configure sua chave da API do logo.dev:**

```bash
cp .env.example .env
# Edite o .env e adicione sua chave:
# LOGODEV_API_KEY=sua_chave_aqui
```

Chave gratuita disponível em [logo.dev](https://www.logo.dev).

## Uso

### Empresa única

```bash
# Mínimo — só o nome (logo.dev vai tentar empresa.com)
logo-scraper --name "Stripe"

# Com URL do site (melhora resolução de domínio no logo.dev + habilita scraping do site)
logo-scraper --name "Nubank" --url "https://nubank.com.br"

# Com todas as três fontes
logo-scraper --name "Spotify" \
             --url "https://spotify.com" \
             --linkedin "https://www.linkedin.com/company/spotify"

# Diretório de saída customizado
logo-scraper --name "Vercel" --url "https://vercel.com" --output "./logos/vercel"

# Chave da API direto no comando (sobrescreve o .env)
logo-scraper --name "Stripe" --logodev-api-key "pk_SUA_CHAVE"
```

### Modo batch

```bash
# Processa várias empresas a partir de um arquivo JSON
logo-scraper --from-file examples/companies.json --output "./output"
```

O arquivo JSON deve ser uma lista de objetos com o campo `name`. `url` e `linkedin` são opcionais:

```json
[
  { "name": "Nubank",  "url": "https://nubank.com.br",  "linkedin": "https://www.linkedin.com/company/nubank" },
  { "name": "Stripe",  "url": "https://stripe.com" },
  { "name": "iFood",                                    "linkedin": "https://www.linkedin.com/company/ifood-" }
]
```

## Rodando os testes

```bash
pytest
```

## Limitações conhecidas

- **LinkedIn bloqueia scraping agressivamente** — espere 403, redirects para login ou status 999. A taxa de sucesso varia e pode cair a zero sem aviso.
- **Scraping de site é heurístico** — páginas que carregam imagens via JavaScript não funcionam (sem browser headless).
- **logo.dev tem limite de requests** no plano gratuito.

## Licença

MIT — veja [LICENSE](LICENSE) para detalhes.
