---
doc_type: attribute_schema
category: Electronics
effective_date: 2026-01-01
source: "CatalogOps internal experimental policy summary"
risk_level: medium
---

# Electronics Attribute Schema

## Common Required Attributes

Electronics listings should provide structured values for:

- brand
- product_type
- model
- key_specification

## Category Specific Requirements

- Mobile Phones require brand, product_type, model, storage_capacity, and network_type.
- Audio requires brand, product_type, model, and connectivity.
- Computers & Accessories requires brand, product_type, model, and processor_or_capacity.
- Cameras requires brand, product_type, model, and resolution_or_mount.
- Storage & Memory requires brand, product_type, storage_capacity, and interface.
- Chargers & Cables requires brand, product_type, connector_type, and power_rating.

## Missing Attribute Handling

If a required attribute is absent from merchant attributes and cannot be inferred from
the title or description, create a missing_attribute issue and cite this schema as
attribute_schema evidence.
