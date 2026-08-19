# Sixty Days repository manifest

This folder is a self-contained candidate root for the independent Sixty Days Git repository.
The original combined implementation remains in ../app/. This copy can be tested, built, and
deployed from app/ without code from another submission.

## Repository boundary

- app/sixty_days/: Sixty Days domain code
- app/spine/: reviewed runtime substrate required by this project
- app/service/sixty_days_routes.py: Sixty Days API only
- app/web/: Sixty Days public and judges pages only
- app/fixtures/, app/scripts/, and app/tests/: Sixty Days evidence and verification

## Independent deployment

- Cloud Run service: sixty-days
- Hosted URL: https://sixty-days-109051079423.us-central1.run.app
- Public identity: sixty-days
- Demo gate: 24/24

Initialize or push only after the independent test, accessibility, container, and demo gates pass.
