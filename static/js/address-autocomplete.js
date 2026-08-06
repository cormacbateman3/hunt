/* Google Places autocomplete for the address form — narrow, and honest
 * about failing.
 *
 * The form works completely without this: typing a plain address is the
 * baseline. When a key is configured the script loads Places and wires
 * line1 as the search box; when the load fails — offline, blocked, a bad
 * key — the page says so in one quiet line instead of degrading silently,
 * which is the difference between a member shrugging and a member filing
 * a bug about a search box that "does nothing".
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

    window.kbInitAddressAutocomplete = function () {
        const line1 = document.querySelector(form.dataset.line1);
        if (!line1 || !window.google || !google.maps || !google.maps.places) {
            say('Address suggestions couldn’t start — typing the address plainly works as normal.');
            return;
        }
        const autocomplete = new google.maps.places.Autocomplete(line1, {
            types: ['address'],
            componentRestrictions: { country: 'us' },
            fields: ['address_components'],
        });
        autocomplete.addListener('place_changed', () => {
            const components = (autocomplete.getPlace() || {}).address_components || [];
            const get = (type, short) => {
                const c = components.find(c => c.types.includes(type));
                return c ? (short ? c.short_name : c.long_name) : '';
            };
            const number = get('street_number');
            const route = get('route');
            if (route) line1.value = (number ? number + ' ' : '') + route;
            const city = get('locality') || get('sublocality') || get('postal_town');
            const cityInput = document.querySelector(form.dataset.city);
            if (city && cityInput) cityInput.value = city;
            const state = get('administrative_area_level_1', true);
            const stateInput = document.querySelector(form.dataset.state);
            if (state && stateInput) stateInput.value = state;
            const zip = get('postal_code');
            const zipInput = document.querySelector(form.dataset.zip);
            if (zip && zipInput) zipInput.value = zip;
        });
    };

    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://maps.googleapis.com/maps/api/js?key=' + encodeURIComponent(key)
        + '&libraries=places&callback=kbInitAddressAutocomplete';
    script.onerror = () => {
        say('Address suggestions couldn’t load — typing the address plainly works as normal.');
    };
    document.head.appendChild(script);
})();
