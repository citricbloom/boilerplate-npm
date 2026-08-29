# Polaris WordPress parity and agency-quality acceptance

## Controlled baseline

The approved static visual baseline is commit `0fc67a8f01dc7bee3b72283dade6a12c134627a5`.

## Required viewports

- 320 x 568
- 375 x 667
- 390 x 844
- 393 x 852
- 430 x 932
- 768 x 1024
- 1024 x 768
- 1440 x 960
- 1920 x 1080

## Visual checks

- full logo remains legible and uncropped
- header, hero, service rows, consultation steps, Why Polaris, footer and persistent CTA retain approved geometry
- text line wrapping and section boundaries remain stable
- mobile and desktop hero crops preserve intended focal points
- lower therapy scene crop preserves the central subjects
- no layout shift after images and WordPress assets load
- no WordPress block/global styles alter the approved design

## Behaviour checks

- mobile menu: open, close, Escape, focus loop, focus return, resize close and scroll restoration
- contact page: reveal form, radio-dependent required fields, invalid state, success state, error state and repeat submission rate limit
- all navigation and footer links
- browser Back and forward navigation
- persistent mobile CTA safe-area spacing and contact-page suppression
- reduced-motion behaviour
- keyboard-only traversal and visible focus

## WordPress editability checks

- save a Home field and verify the public page changes
- save another tab and confirm the Home field is preserved
- edit a Service and verify the homepage row and service accordion
- edit a Team member and verify the homepage people strip and team page
- replace mobile and desktop hero images independently
- edit primary/footer menus without changing the front-end component styling
- revert all QA changes and verify baseline restoration

## Technical checks

- PHP lint on every PHP file
- JavaScript parse check
- install/activate on current WordPress and PHP 8.3
- clean debug log
- valid ZIP structure and checksums
- local assets only; no production dependency on temporary CDN URLs
- form nonce, honeypot, input validation, rate limiting and recipient validation
- no preview-only text, no forced noindex in production, and no unapproved analytics
