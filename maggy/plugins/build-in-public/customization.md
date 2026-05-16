# Build-in-Public Customization
# Add your personal guidelines here. The plugin reads this file when generating posts.

## Channel Voice

### LinkedIn
- Longer form, 2-4 paragraphs, professional and insightful
- Teaches something, not just "I shipped X"
- Write like you're explaining to a senior engineer friend
- Always include a link to the relevant GitHub repo or project
- NO coding stats (no "96 files, 14 commits" — that's lame)
- NO hype sludge ("I'm excited to announce...")
- Break up text with line breaks for readability

### X (Twitter)
- Sharp, punchy, 280 chars max
- ALWAYS include a clickout link (e.g. github.com/alinaqi/maggy)
- One insight per post, no threads unless truly multi-part
- Write like you're texting a builder friend
- No hashtag stuffing

## Content Guidelines

### What to Share
- Technical decisions and reasoning
- Architecture insights
- Counter-intuitive findings
- Lessons learned from failures

### What to NEVER Share
- Revenue, user counts, valuation
- Customer names or client details
- Internal URLs, API keys
- Roadmap promises
- Coding stats (lines, files, commits — nobody cares)

## Brand Rules
# Company names are anonymized by default (zenloop -> "a CX SaaS platform")
# To explicitly talk about a brand:
#   /build-in-public add brand <brand-name>
# To add a clickout link for a project:
#   /build-in-public add clickouts to <url>

explicit_brands: []
explicit_clickouts:
  - "github.com/alinaqi/maggy"
