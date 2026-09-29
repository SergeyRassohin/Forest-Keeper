# Forest Keeper — Site history and requirements

## Published prototype
A previously published Forest Keeper site existed at:

`https://forest-keeper-data.sergey-rassohin0511.chatgpt.site`

This URL is historical project context and should be treated as a deployment reference until the current deployment is re-verified.

## Public site structure
The previously discussed multi-page structure contained:

- `/` — main landing page;
- `/capabilities` — capabilities;
- `/workflow` — how Forest Keeper works;
- `/security` — security / on-premises positioning;
- `/pilot` — pilot / first implementation proposal.

The public site presented Forest Keeper as a vendor-neutral layer for matching, checking and governing enterprise data without replacing the customer's existing ERP/PLM/MDM/WMS/CRM/EAM landscape.

## Visual direction
The visual requirements discussed for the site were:

- a forest background / forest identity across all pages;
- consistent typography and font sizing;
- readable text over the background;
- richer, polished page transitions rather than plain navigation;
- responsive layout;
- pages should remain extensible rather than being hard-coded dead ends.

The desired impression was premium and deliberate, not a generic corporate template.

## Protected sections
Two separate protected areas were discussed:

### `/edit`
An editor area intended to evolve toward a WYSIWYG experience where content could be changed without editing source manually.

Desired capabilities included:
- edit text;
- change font size and type;
- change backgrounds;
- insert new content blocks;
- create new pages;
- work more like PowerPoint / a visual site builder than a raw-code editor.

### `/service`
A service / engineering area with separate authorization.

The discussed content included:
- project/service information;
- source code access or links to source control;
- archived source material;
- Git repository reference;
- engineering/service controls that should not be visible to ordinary site visitors.

`/edit` and `/service` were intended to be protected independently from the public pages.

## Authorization UX
For protected areas, the password field should include a show/hide control (eye icon).

A previously observed implementation problem was that the service login used PBKDF2 with 210,000 iterations while the execution environment imposed a 100,000-iteration limit. This broke the service login and must not be repeated blindly in a rebuilt version. Authentication parameters must be compatible with the actual runtime and should be tested end-to-end.

## Content themes from the original site
The site previously covered at least these product messages:

- Forest Keeper concept;
- comparison / matching of data from different systems;
- operating modes;
- on-premises and security positioning;
- pilot implementation.

## Repository / Project Portal direction
The long-term direction is to make GitHub the engineering source of truth for Forest Keeper, with the website, documentation, requirements and source code stored together in the private repository.

The Project Portal idea should provide a coherent entry point to:
- current requirements;
- architecture;
- decisions;
- site source;
- documentation;
- testing/security materials;
- deployed-site reference;
- Git history.

## Current migration status
This document preserves the known site structure and requirements from prior work. It does **not** prove that the original site source code has already been recovered into this repository.

Next migration step for the site:
1. locate the original site source or exported project artifacts;
2. add them under a dedicated application/site directory;
3. verify the historical deployment URL;
4. record local run/build instructions;
5. test public routes plus `/edit` and `/service` authentication;
6. then wire the site into the repository-wide Project Portal/index.
