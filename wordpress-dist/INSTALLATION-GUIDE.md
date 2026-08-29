# Polaris Wellbeing WordPress installation guide

Package version: 1.0.1  
Controlled visual baseline: Polaris static v0.3.4, commit `0fc67a8f01dc7bee3b72283dade6a12c134627a5`

## Files

- `polaris-wellbeing-theme-v1.0.1.zip` - controlled front-end theme
- `polaris-core-v1.0.1.zip` - content model, admin editing interface and enquiry handler
- `polaris-wordpress-playground-bundle-v1.0.1.zip` - disposable browser QA environment, not for production hosting

## GoDaddy staging installation

1. Create a full GoDaddy backup or staging clone before changing the current site.
2. In WordPress, open **Appearance > Themes > Add New > Upload Theme**.
3. Upload `polaris-wellbeing-theme-v1.0.1.zip` and activate it.
4. Open **Plugins > Add New > Upload Plugin**.
5. Upload `polaris-core-v1.0.1.zip` and activate it.
6. Open **Settings > Permalinks** and press **Save Changes** once.
7. Open **Polaris Content** in the WordPress admin menu. Review every tab and save approved contact, privacy and urgent-support information.
8. Review **Appearance > Menus**. The package creates and assigns the primary and footer menus automatically; confirm their order before launch.
9. Open every page on mobile and desktop. Do not make the production domain public until the acceptance tests below pass.

The setup routine is idempotent. It creates missing pages, menu entries, services and initial team records without overwriting existing records with matching names.

## Editing model

Routine content is edited through **Polaris Content**, **Services**, **Team**, **Programmes**, and WordPress menus. The public layout, type scale, colours, spacing, breakpoints, button geometry and mobile behaviour are controlled by the theme and should not be edited through arbitrary page-builder controls.

Editable content includes:

- headings, body copy and CTA labels
- hero and section images
- service rows and service descriptions
- team names, roles, biographies, qualifications, languages and portraits
- contact details, WhatsApp number, phone number and form recipient
- urgent-support wording and privacy consent wording
- footer copy and navigation

The two homepage hero image fields are intentionally separate. Use a portrait/mobile crop for the mobile field and a square/landscape crop for the desktop field.

## Email delivery

The enquiry form uses WordPress `wp_mail()` and does not store submissions in the database. Before launch:

1. Configure an authenticated SMTP or transactional-email service compatible with the Polaris domain.
2. Set the receiving mailbox in **Polaris Content > Global > Form recipient email**.
3. Submit successful tests from Safari, Chrome and a private/incognito browser.
4. Confirm receipt, Reply-To behaviour, spam-folder placement and failure messaging.

Do not rely on an untested default GoDaddy/PHP mail configuration.

## Privacy and safety launch gates

- Review and approve the Privacy Policy page with the appropriate Polaris adviser.
- Confirm the form data-retention and mailbox-access policy.
- Verify Malta emergency and urgent-support wording.
- Do not enable analytics that capture form values or health-related URL parameters.
- Keep staging set to discourage search-engine indexing until launch approval.

## Cache and optimisation

After each release, purge GoDaddy, WordPress and CDN caches. Do not install optimisation plugins that combine or delay the controlled CSS/JavaScript without repeating the visual and behavioural QA suite.

## Minimum launch acceptance

- no top sticky CTA
- complete Polaris logo at every breakpoint
- bottom mobile CTA visible except on the contact page
- no horizontal overflow from 320 px upward
- mobile navigation opens, traps focus, closes with Escape and restores scrolling
- all internal routes return 200 and browser Back works
- hero switches to the correct mobile/desktop crop at 760 px
- form validates the chosen contact method and produces a verified email
- no PHP warnings, JavaScript errors or failed local asset requests
- approved screenshots match the controlled v0.3.4 baseline within the documented browser-rendering tolerance
