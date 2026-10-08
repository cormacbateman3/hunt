/* Google Places address search for the address form — narrow, and honest
 * about failing.
 *
 * The form works completely without this: typing a plain address is the
 * baseline. When a key is configured the script loads Places and puts a
 * "Find your address" search box above the street line; picking a result
 * fills the street, city, state and ZIP fields, which stay ordinary inputs
 * the member can still correct. When the load fails — offline, blocked, a
 * bad key — the page says so in one quiet line instead of degrading silently.
 *
 * Uses PlaceAutocompleteElement (Places API "New"). The old
 * google.maps.places.Autocomplete can't be loaded by keys created after
 * March 2025, so a new project key would have broken it (W1.11). The key
 * needs "Places API (New)" enabled and should be restricted to the site's
 * domain, since it is sent to browsers.
 *
 * Wire-up: a <form data-address-autocomplete> carrying data attributes —
 *   data-places-key, data-line1, data-city, data-state, data-zip —
 * and, optionally, an element with [data-places-notice] for the failure line.
 */
(function () {
    'use strict';

    const form = document.querySelector('[data-address-autocomplete]');
    if (!form) return;
    const key = form.dataset.placesKey;
    if (!key) return;

    const say = (message) => {
        const notice = document.querySelector('[data-places-notice]');
        if (!notice) return;
        notice.textContent = message;
        notice.hidden = false;
    };
    const field = (selector) => (selector ? document.querySelector(selector) : null);

    function fill(components) {
        // components: [{ longText, shortText, types }]
        const get = (type, short) => {
            const c = components.find((part) => (part.types || []).includes(type));
            return c ? (short ? c.shortText : c.longText) : '';
        };
        const number = get('street_number');
        const route = get('route');
        const line1 = field(form.dataset.line1);
        if (route && line1) line1.value = (number ? number + ' ' : '') + route;
        const city = get('locality') || get('sublocality') || get('postal_town');
        const cityInput = field(form.dataset.city);
        if (city && cityInput) cityInput.value = city;
        const state = get('administrative_area_level_1', true);
        const stateInput = field(form.dataset.state);
        if (state && stateInput) stateInput.value = state;
        const zip = get('postal_code');
        const zipInput = field(form.dataset.zip);
        if (zip && zipInput) zipInput.value = zip;
        if (line1) line1.focus();
    }

    async function placeFrom(event) {
        // Newer releases send `placePrediction` with gmp-select; the earlier
        // gmp-placeselect sent `place` directly. Accept either.
        if (event.placePrediction) return event.placePrediction.toPlace();
        return event.place || null;
    }

    window.kbInitAddressAutocomplete = async function () {
        const line1 = field(form.dataset.line1);
        try {
            const { PlaceAutocompleteElement } = await google.maps.importLibrary('places');
            const search = new PlaceAutocompleteElement({ includedRegionCodes: ['us'] });
            search.id = 'kb-address-search';
            search.classList.add('kb-address-search');

            const label = document.createElement('label');
            label.className = 'kb-label';
            label.htmlFor = search.id;
            label.textContent = 'Find your address';
            const wrap = document.createElement('div');
            wrap.className = 'if-field';
            wrap.append(label, search);
            const lineField = line1 ? line1.closest('.if-field') : null;
            if (lineField) lineField.before(wrap);
            else form.prepend(wrap);

            const onPick = async (event) => {
                try {
                    const place = await placeFrom(event);
                    if (!place) return;
                    await place.fetchFields({ fields: ['addressComponents'] });
                    fill(place.addressComponents || []);
                } catch (err) {
                    say('That address couldn’t be filled in — typing it plainly works as normal.');
                }
            };
            search.addEventListener('gmp-select', onPick);
            search.addEventListener('gmp-placeselect', onPick);
        } catch (err) {
            say('Address suggestions couldn’t start — typing the address plainly works as normal.');
        }
    };

    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://maps.googleapis.com/maps/api/js?key=' + encodeURIComponent(key)
        + '&v=weekly&loading=async&callback=kbInitAddressAutocomplete';
    script.onerror = () => {
        say('Address suggestions couldn’t load — typing the address plainly works as normal.');
    };
    document.head.appendChild(script);
})();
