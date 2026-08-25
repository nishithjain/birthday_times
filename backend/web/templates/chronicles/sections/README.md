# Modular Sections

## Eagle / Logo

- Partial: `eagle_logo.html`
- Consumes: the existing `chronicle.illustrations.masthead` Eagle illustration payload
- CSS: `sections/eagle_logo.css`
- Standalone test page: `test_pages/test_eagle_logo.html`
- Development route: `/dev/sections/eagle-logo`
- Dimensions: `458 x 100`

Era mapping:

- `1950-1969` -> `eagle.png`
- `1970-1989` -> `eagle_globe.png`
- `1990-2004` -> `newspaper_globe.png`
- `2005-2014` -> `circular_chronicle_seal.png`
- `2015-present` -> `bc_logo.png`

### Eagle / Logo Visual Review

- Development route: `/dev/sections/eagle-logo-review`
- Default cases: `1950, 1960, 1982, 2005, 2015`
- Default interval: `1000 ms`
- Optional parameters: `interval=1500` and `years=1950,1960,1982`

The modular `masthead.html` no longer owns the Eagle artwork. The standalone
Eagle / Logo component reuses IllustrationService's existing payload and era
variant resolution. The legacy production templates remain unchanged.

## Extra Component

- Partial: `extra.html`
- Consumes: `chronicle.person.birth_date_display`
- CSS: `sections/extra.css`
- Standalone test page: `test_pages/test_extra.html`
- Development route: `/dev/sections/extra`
- Visual review route: `/dev/sections/extra-review`
- Dimensions: `230 x 100`

The Extra component is an independent decorative callout. It is not yet part
of the final master top-row layout.

Its `SPECIAL BIRTHDAY` line uses the active newspaper style ID and the
centralized monochrome ornament mapping: `★` for 1950/1960, `✶` for 1970/1980,
`◆` for 1990/1995/2000, `❖` for 2005/2010, and `•` for 2015 and later.

## Masthead

- Partial: `masthead.html`
- Consumes: `chronicle.newspaper_style.id`, `chronicle.calendar.day_of_week`, and `chronicle.person.birth_date_display`
- CSS: `sections/masthead.css`
- Standalone route: `/dev/sections/masthead`
- Visual review route: `/dev/sections/masthead-review`
- Dimensions: `920 x 150`

The modular masthead contains only the publication identity. Weather, Eagle /
Logo, and Extra are separate components and are not embedded here.

The Masthead review runner covers the 18 configured dates, including era
boundaries, long month names, leap day, and short/long date layouts. It uses
one iframe and a `1000 ms` default interval at `/dev/sections/masthead-review`.

The publication title is resolved from the existing style ID:

- `1950`, `1960` -> `The Birthday Gazette`
- `1970`, `1980` -> `The Birthday Chronicle`
- `1990`, `1995`, `2000` -> `The Birthday Herald`
- `2005`, `2010` -> `The Birthday Edition`
- `2015` and future styles -> `The Birthday Times`

Unexpected style IDs use `The Birthday Times` as the deterministic fallback.
The secondary tagline remains `WHAT THE WORLD WAS LIKE WHEN YOU WERE BORN`.

## Arrival / Birth Story

- Partial: `arrival_president.html`
- Consumes: ArrivalService Birth Story fields, Chronicle calendar/date data, location data, and PresidentService payload
- CSS: `sections/arrival.css`
- Standalone route: `/dev/sections/arrival`
- Visual review route: `/dev/sections/arrival-review`
- Dimensions: `920 x 310`

The component is organized as News Dispatch, Birth Story, and From The White
House columns. The existing Arrival fitting hook measures the deterministic
story content in the real DOM and records its fit result.

News Dispatch uses the existing style ID to select the approved artwork and
label: telegram/wire service/news press/news flash for 1950-1980, computer
bulletin for 1990/1995, news alert for 2000/2005, digital dispatch for 2010,
and news update for 2015 and later. The artwork is rendered with preserved
aspect ratio in a `124 x 80` slot using multiply blending for the newspaper
paper background.
