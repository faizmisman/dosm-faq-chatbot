# Dataset Card – Monthly Unemployment by Duration (lfs_month_duration)

- Source URL: https://open.dosm.gov.my/data-catalogue/lfs_month_duration
- License: Open Government Data (DOSM portal)
- Last updated (portal): 2025-11-10 12:00 (MYT)   <!-- verify on portal -->
- Refresh cadence: Monthly

- Fields:
  - date (YYYY-MM-DD; monthly, day fixed to 01)
  - unemployed (thousand persons)
  - unemployed_active (thousand persons)
  - unemployed_inactive (thousand persons)
  - unemployed_active_3mo (active, <3 months; thousand persons)
  - unemployed_active_6mo (active, 3–6 months; thousand persons)
  - unemployed_active_12mo (active, 6–12 months; thousand persons)
  - unemployed_active_long (active, >12 months; thousand persons)

- Known gaps/quirks:
  - Series break around 2025: benchmark changes from 2010 Census to 2020 Census (levels may shift).
  - Independent rounding: subtotals may not equal totals exactly.
  - All count variables are in **thousand persons**.

- Added on: 2025-11-21