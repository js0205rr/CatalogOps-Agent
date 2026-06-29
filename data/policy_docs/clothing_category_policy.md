---
doc_type: category_policy
category: Clothing & Accessories
effective_date: 2026-01-01
source: "CatalogOps internal policy summary based on public marketplace listing rules"
risk_level: medium
---

# Clothing Category Policy

## Scope

This policy applies to products under Clothing & Accessories. Use the product title,
description, and provided attributes to determine the most specific leaf category.

## Category Routing

- Apparel is a fallback category for clothing items whose specific product type is unclear.
- Tops include shirts, t-shirts, tees, blouses, hoodies, sweatshirts, jackets, and coats.
- Bottoms include jeans, trousers, pants, leggings, shorts, joggers, and palazzos.
- Dresses include dresses, gowns, sarees, kurtas, kurtis, lehengas, skirts, rompers,
  jumpsuits, and swimwear.
- Clothing Sets include coordinated outfits, suits, tracksuits, night suits, sleep suits,
  and multi-piece apparel sets.
- Innerwear includes bras, briefs, underwear, lingerie, vests, socks, and close-to-body apparel.
- Shoes include sneakers, sandals, slippers, boots, loafers, heels, and other footwear.
- Bags include handbags, backpacks, wallets, purses, clutches, and totes.
- Accessories include sunglasses, belts, watches, jewelry, scarves, caps, hats, ties,
  hairbands, headbands, and similar wearable accessories.

## Mismatch Rule

If product text clearly indicates one leaf category but seller_category points to another
leaf category, mark category_mismatch when category confidence is high. If the product
type is unclear or multiple categories are plausible, send the item to human_review.
