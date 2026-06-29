---
doc_type: category_policy
category: Electronics
effective_date: 2026-01-01
source: "CatalogOps internal experimental policy summary"
risk_level: medium
---

# Electronics Category Policy

## Scope

This policy applies to consumer electronics, digital devices, accessories, and
electronic components. Use product title, description, and merchant attributes to
route to the most specific supported category.

## Category Routing

- Mobile Phones include smartphones, feature phones, Android phones, iPhones, and handsets.
- Audio includes headphones, earphones, earbuds, speakers, soundbars, and Bluetooth audio devices.
- Computers & Accessories includes laptops, monitors, keyboards, mice, routers, hard drives, SSDs, and computer peripherals.
- Cameras includes digital cameras, webcams, CCTV cameras, lenses, tripods, and camcorders.
- Storage & Memory includes memory cards, microSD cards, SD cards, flash drives, pen drives, hard drives, and SSDs sold as storage devices.
- Chargers & Cables includes chargers, adapters, power banks, USB cables, Type-C cables, Lightning cables, and charging accessories.
- Use the top-level Electronics category only when the listing is clearly electronic but the product type is not specific enough.

## Decision Rule

If product text clearly indicates a specific Electronics subcategory but seller_category
points to a different top-level category or unrelated Electronics subcategory, create
a category_mismatch issue with product text evidence. If a product can reasonably fit
multiple electronics accessory categories, downgrade to human_review.
