---
name: strapi-gcs-security
description: GCS upload security rule — never expose files publicly, always use signed URLs
---

# Strapi GCS Security

## Rule (MANDATORY)
- **NEVER** use `publicFiles: true` in `@strapi-community/strapi-provider-upload-google-cloud-storage` config (`apps/admin/config/plugins.ts`)
- Sets `allUsers: READER` on all uploaded files — documents (land registers, contracts) exposed to public internet

## Solution
- Always `publicFiles: false`
- Serve via Signed URLs: `/v1/assets/:id/public`
- Bucket: enable "Uniform Bucket-Level Access"
