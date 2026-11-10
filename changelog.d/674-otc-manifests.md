### Manifests voor staging-otc en production-otc (#674)
- De cluster `production` is op 2026-09-15 uitgezet; de SDP-productie is `production-otc`, met `staging-otc` ervoor.
  `manifests/staging-otc` en `manifests/production-otc` zijn voorbereid op basis van playground: vaste release-pin,
  `strategy: Recreate`, `APP_ENV=production`, opschoning na de bewaartermijn aan, host
  `onderwijsdata-chat.<staging|production>.sdp.surf.nl` (de conventie van andere OTC-tenants, zoals edugenai en han-ai-assist).
- Er rolt nog niets uit: de registratie in `kubernetes-clusters`, de tenant en `secret.yaml` ontbreken nog (zie #674).
