// backend/web/static/js/app.js

document.addEventListener('DOMContentLoaded', function () {
    // Date input formatting helper
    const dateInput = document.getElementById('birth_date');
    if (dateInput) {
        dateInput.addEventListener('input', function (e) {
            // Auto-format DD-MM-YYYY as user types
            let value = this.value.replace(/[^0-9]/g, '');
            if (value.length >= 8) {
                // Format as DD-MM-YYYY
                let day = value.substring(0, 2);
                let month = value.substring(2, 4);
                let year = value.substring(4, 8);
                if (day.length === 2 && month.length === 2 && year.length === 4) {
                    // Check if it's a valid date
                    const dateObj = new Date(year, month - 1, day);
                    if (dateObj.getDate() == day && dateObj.getMonth() == month - 1) {
                        // Valid date, keep as is
                    }
                }
            }
        });

        // Add placeholder hint
        dateInput.placeholder = 'DD-MM-YYYY';
    }

    // Print button
    const printBtn = document.querySelector('.btn-print');
    if (printBtn) {
        printBtn.addEventListener('click', function () {
            window.print();
        });
    }

    fitArrivalArticle();
    fitWorldNews();
    fitAroundThisTime();
    fitZodiacSection();
    fitMoviesSection();
    fitMusicSection();
    fitWeatherCopy();
});

function checkWeatherDimensions() {
    const weather = document.querySelector('[data-weather-component]');
    if (!weather) return;
    const rect = weather.getBoundingClientRect();
    const dimensionsOk = Math.abs(rect.width - 228) < 0.5 && Math.abs(rect.height - 100) < 0.5;
    const overflow = weather.scrollWidth > weather.clientWidth || weather.scrollHeight > weather.clientHeight;
    if (!dimensionsOk) console.warn('WEATHER DIMENSIONS', { width: rect.width, height: rect.height });
    if (overflow) console.warn('WEATHER OVERFLOW', { clientWidth: weather.clientWidth, scrollWidth: weather.scrollWidth, clientHeight: weather.clientHeight, scrollHeight: weather.scrollHeight });
    weather.dataset.weatherDimensions = dimensionsOk ? 'ok' : 'invalid';
    weather.dataset.weatherOverflow = overflow ? 'true' : 'false';
}

async function fitMeasuredCandidates({ candidates, targetFill, minFill, maxFill, maxAttempts, apply, measure }) {
    let best = null;
    const attempts = [];
    for (const candidate of candidates.slice(0, maxAttempts)) {
        apply(candidate);
        void document.body.offsetHeight;
        const result = measure();
        attempts.push({ candidate, ...result, overflow: result.fillRatio > maxFill });
        if (result.fillRatio <= maxFill && (!best || Math.abs(result.fillRatio - targetFill) < Math.abs(best.result.fillRatio - targetFill))) best = { candidate, result };
        if (result.fillRatio >= minFill && result.fillRatio <= maxFill) return { ...best, attempts, stoppedEarly: true };
    }
    return { ...best, attempts, stoppedEarly: false };
}

async function fitMusicSection() {
    const article = document.querySelector('.article-music');
    const content = article && article.querySelector('[data-music-fit-content]');
    const data = article && article.querySelector('[data-music-candidates]');
    const body = content && content.querySelector('[data-music-body]');
    if (!article || !content || !data || !body) return;
    const candidates = JSON.parse(data.textContent);
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    const image = article.querySelector('img');
    if (image && !image.complete) await new Promise(resolve => { image.addEventListener('load', resolve, { once: true }); image.addEventListener('error', resolve, { once: true }); });
    await new Promise(requestAnimationFrame);
    const bottom = article.getBoundingClientRect().bottom;
    const availableHeight = Math.max(0, bottom - content.getBoundingClientRect().top - (parseFloat(getComputedStyle(article).paddingBottom) || 0));
    const result = await fitMeasuredCandidates({
        candidates,
        targetFill: 0.91,
        minFill: 0.84,
        maxFill: 0.96,
        maxAttempts: 3,
        apply: candidate => { body.textContent = candidate.bodyText; },
        measure: () => ({ contentHeight: content.scrollHeight, fillRatio: availableHeight ? content.scrollHeight / availableHeight : 1 }),
    });
    if (result.candidate) body.textContent = result.candidate.bodyText;
    article.dataset.musicFit = JSON.stringify({ availableHeight, contentHeight: result.result.contentHeight, fillRatio: result.result.fillRatio, mentionLimit: result.candidate.mentionLimit, attempts: result.attempts, stoppedEarly: result.stoppedEarly });
    content.classList.remove('music-fit-pending');
}

async function fitMoviesSection() {
    const TARGET_FILL = 0.93;
    const MAX_FILL = 0.97;
    const article = document.querySelector('.article-movies');
    const content = article && article.querySelector('[data-movies-fit-content]');
    const data = article && article.querySelector('[data-movie-candidates]');
    const list = content && content.querySelector('.movie-secondary-list');
    const items = list ? [...list.querySelectorAll('[data-movie-item]')] : [];
    if (!article || !content || !data || !list) return;
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    const image = content.querySelector('img');
    if (image && !image.complete) await new Promise(resolve => { image.addEventListener('load', resolve, { once: true }); image.addEventListener('error', resolve, { once: true }); });
    await new Promise(requestAnimationFrame);
    const candidates = JSON.parse(data.textContent);
    const bottom = article.getBoundingClientRect().bottom;
    const availableHeight = Math.max(0, bottom - content.getBoundingClientRect().top - (parseFloat(getComputedStyle(article).paddingBottom) || 0));
    const measure = () => ({ contentHeight: content.scrollHeight, fillRatio: availableHeight ? content.scrollHeight / availableHeight : 1 });
    let best = null;
    for (let count = 0; count <= Math.min(items.length, candidates.length - 1); count += 1) {
        items.forEach((item, index) => { item.style.display = index < count ? '' : 'none'; });
        void content.offsetHeight;
        const result = measure();
        if (result.fillRatio <= MAX_FILL && (!best || Math.abs(result.fillRatio - TARGET_FILL) < Math.abs(best.fillRatio - TARGET_FILL))) best = { count, ...result };
    }
    best = best || { count: 0, ...measure() };
    items.forEach((item, index) => { item.style.display = index < best.count ? '' : 'none'; });
    article.dataset.movieFit = JSON.stringify({ candidateCount: candidates.length, secondaryCount: best.count, availableHeight, contentHeight: best.contentHeight, fillRatio: best.fillRatio });
}

async function fitZodiacSection() {
    const TARGET_FILL = 0.93;
    const MAX_FILL = 0.97;
    const article = document.querySelector('[data-zodiac-fit-container]');
    const content = article && article.querySelector('[data-zodiac-fit-content]');
    const box = article && article.querySelector('[data-zodiac-image-box]');
    const image = box && box.querySelector('img');
    const data = document.querySelector('[data-zodiac-candidates]');
    const intro = article && article.querySelector('[data-zodiac-intro]');
    const fortune = article && article.querySelector('[data-zodiac-fortune]');
    const optional = article && [...article.querySelectorAll('[data-zodiac-optional]')];
    if (!article || !content || !box || !data || !intro || !fortune) return;
    let candidates;
    try {
        candidates = JSON.parse(data.textContent);
    } catch (error) {
        return;
    }
    if (!Array.isArray(candidates) || !candidates.length) return;
    article.classList.remove('zodiac-fit--tight');
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    if (image && !image.complete) await new Promise(resolve => { image.addEventListener('load', resolve, { once: true }); image.addEventListener('error', resolve, { once: true }); });
    if (image && image.naturalWidth && image.naturalHeight) {
        const ratio = image.naturalWidth / image.naturalHeight;
        const maxWidth = 175;
        const maxHeight = 150;
        const width = ratio >= 1 ? Math.min(maxWidth, maxHeight * ratio) : maxHeight * ratio;
        box.style.width = `${width}px`;
        box.style.height = `${width / ratio}px`;
        box.style.aspectRatio = `${ratio}`;
    }
    await new Promise(requestAnimationFrame);
    const bottom = article.getBoundingClientRect().bottom;
    const availableHeight = Math.max(0, bottom - content.getBoundingClientRect().top - (parseFloat(getComputedStyle(article).paddingBottom) || 0));
    const measure = () => ({ contentHeight: content.scrollHeight, fillRatio: availableHeight ? content.scrollHeight / availableHeight : 1 });
    const attempts = [];
    let best = null;
    for (const candidate of candidates.slice(0, 3)) {
        intro.textContent = candidate.introText;
        fortune.textContent = candidate.fortuneText;
        optional.forEach(item => { item.style.display = 'none'; });
        void content.offsetHeight;
        const result = measure();
        attempts.push({ id: candidate.id, ...result, overflow: result.fillRatio > MAX_FILL });
        if (result.fillRatio <= MAX_FILL && (!best || Math.abs(result.fillRatio - TARGET_FILL) < Math.abs(best.fillRatio - TARGET_FILL))) best = { candidate, ...result, optionalCount: 0 };
        if (result.fillRatio >= 0.88 && result.fillRatio <= MAX_FILL) break;
    }
    if (!best) {
        article.classList.add('zodiac-fit--tight');
        best = { candidate: candidates[candidates.length - 1], ...measure(), optionalCount: 0 };
    }
    intro.textContent = best.candidate.introText;
    fortune.textContent = best.candidate.fortuneText;
    for (let count = 0; count <= optional.length; count += 1) {
        optional.forEach((item, index) => { item.style.display = index < count ? '' : 'none'; });
        void content.offsetHeight;
        const result = measure();
        if (result.fillRatio <= MAX_FILL && Math.abs(result.fillRatio - TARGET_FILL) < Math.abs(best.fillRatio - TARGET_FILL)) best = { candidate: best.candidate, ...result, optionalCount: count };
    }
    optional.forEach((item, index) => { item.style.display = index < best.optionalCount ? '' : 'none'; });
    article.dataset.zodiacFit = JSON.stringify({ availableHeight, contentHeight: best.contentHeight, fillRatio: best.fillRatio, templateId: best.candidate.id, optionalCount: best.optionalCount, attempts });
    article.classList.remove('zodiac-fit-pending');
}

async function fitAroundThisTime() {
    const TARGET_FILL = 0.89;
    const MAX_FILL = 0.93;
    const content = document.querySelector('[data-around-container]');
    const article = content && content.closest('.article-around');
    const data = document.querySelector('[data-around-candidates]');
    const items = content && [...content.querySelectorAll('[data-around-item]')];
    if (!content || !article || !data) return;
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await new Promise(requestAnimationFrame);
    const candidates = JSON.parse(data.textContent);
    const bottom = article.getBoundingClientRect().bottom;
    const availableHeight = Math.max(0, bottom - content.getBoundingClientRect().top - (parseFloat(getComputedStyle(article).paddingBottom) || 0));
    const measure = () => ({ contentHeight: content.scrollHeight, fillRatio: availableHeight ? content.scrollHeight / availableHeight : 1 });
    const attempts = [];
    const render = count => {
        items.forEach((item, index) => { item.style.display = index < count ? '' : 'none'; });
        void content.offsetHeight;
        const result = measure();
        attempts.push({ count, ...result, overflow: result.fillRatio > MAX_FILL });
        return result;
    };
    let best = null;
    for (let count = 0; count <= Math.min(items.length, candidates.length - 1); count += 1) {
        const result = render(count);
        if (result.fillRatio <= MAX_FILL && (!best || Math.abs(result.fillRatio - TARGET_FILL) < Math.abs(best.fillRatio - TARGET_FILL) || (Math.abs(result.fillRatio - TARGET_FILL) === Math.abs(best.fillRatio - TARGET_FILL) && count > best.count))) {
            best = { count, ...result };
        }
    }
    best = best || { count: 0, ...render(0) };
    render(best.count);
    article.dataset.aroundFit = JSON.stringify({ candidateCount: candidates.length, secondaryCount: best.count, availableHeight, contentHeight: best.contentHeight, fillRatio: best.fillRatio, attempts });
    content.classList.remove('around-fit-pending');
}

async function fitWorldNews() {
    const container = document.querySelector('[data-world-news-container]');
    const data = document.querySelector('[data-world-news-candidates]');
    const content = container && container.querySelector('[data-world-news-content]');
    const list = content && content.querySelector('.headline-list');
    const items = list && [...list.querySelectorAll('[data-world-news-item]')];
    if (!container || !data || !content || !list || !items.length) return;
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await new Promise(requestAnimationFrame);
    const candidates = JSON.parse(data.textContent);
    const bottom = container.getBoundingClientRect().bottom;
    const paddingBottom = parseFloat(getComputedStyle(container).paddingBottom) || 0;
    const availableHeight = Math.max(0, bottom - content.getBoundingClientRect().top - paddingBottom);
    const measure = () => ({ contentHeight: list.scrollHeight, fillRatio: availableHeight ? list.scrollHeight / availableHeight : 1 });
    const attempts = [];
    const render = (count, descriptions) => {
        container.classList.toggle('world-news--descriptions', descriptions);
        items.forEach((item, index) => { item.style.display = index < count ? '' : 'none'; });
        void container.offsetHeight;
        const measurement = measure();
        attempts.push({ count, descriptions, ...measurement, overflow: measurement.fillRatio > 0.97 });
        return measurement;
    };
    let best = null;
    for (let count = 1; count <= Math.min(candidates.length, items.length); count += 1) {
        const measurement = render(count, false);
        if (measurement.fillRatio <= 0.97) best = { count, descriptions: false, measurement };
    }
    if (!best || best.measurement.fillRatio < 0.82) {
        for (let count = 1; count <= Math.min(candidates.length, items.length); count += 1) {
            const measurement = render(count, true);
            if (measurement.fillRatio <= 0.97 && (!best || Math.abs(measurement.fillRatio - 0.90) < Math.abs(best.measurement.fillRatio - 0.90))) {
                best = { count, descriptions: true, measurement };
            }
        }
    }
    if (!best) best = { count: 1, descriptions: false, measurement: render(1, false) };
    render(best.count, best.descriptions);
    container.dataset.worldNewsFit = JSON.stringify({
        candidateCount: candidates.length,
        displayCount: best.count,
        availableHeight,
        contentHeight: best.measurement.contentHeight,
        fillRatio: best.measurement.fillRatio,
        summariesUsed: best.descriptions,
        attempts,
    });
    container.classList.remove('world-news-fit-pending');
}

async function fitPresidentContext(container) {
    const message = container.querySelector('[data-president-context-fit]');
    const data = container.querySelector('[data-president-context-candidates]');
    const finish = (result, details = {}) => {
        Object.entries({
            ...details,
            fitResult: result,
            fitComplete: 'true',
        }).forEach(([key, value]) => { message.dataset[`presidentContext${key[0].toUpperCase()}${key.slice(1)}`] = String(value); });
        container.dataset.presidentContextFitStatus = result;
        container.dataset.presidentContextFitComplete = 'true';
        container.dispatchEvent(new CustomEvent('president-context-fit-complete', { bubbles: true }));
        if (window.parent !== window) window.parent.postMessage({ type: 'president-context-fit-complete' }, window.location.origin);
    };
    if (!message || !data) return;
    let candidates;
    try {
        candidates = JSON.parse(data.textContent);
    } catch (error) {
        finish('no_candidates', { attemptCount: 0 });
        return;
    }
    if (!Array.isArray(candidates) || !candidates.length) {
        finish('no_candidates', { attemptCount: 0 });
        return;
    }
    // Candidates arrive sorted longest -> shortest; start at the server-selected
    // candidate and only step to shorter ones, never above the server budget.
    const estimatedId = message.dataset.presidentContextEstimatedId;
    const startIndex = Math.max(0, candidates.findIndex(candidate => candidate.id === estimatedId));
    const order = candidates.slice(startIndex);
    if (!order.length) {
        finish('no_candidates', { attemptCount: 0 });
        return;
    }
    if (container.dataset.presidentContextFitComplete === 'true') return;
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await new Promise(requestAnimationFrame);
    const attempts = [];
    let selected = null;
    for (const candidate of order) {
        message.textContent = candidate.text;
        await new Promise(requestAnimationFrame);
        const clientWidth = message.clientWidth;
        const scrollWidth = message.scrollWidth;
        const clientHeight = message.clientHeight;
        const scrollHeight = message.scrollHeight;
        const heightUtilization = clientHeight > 0 ? scrollHeight / clientHeight : null;
        const widthFits = scrollWidth <= clientWidth + 1;
        const heightFits = scrollHeight <= clientHeight + 1;
        const safeHeight = heightUtilization !== null && heightUtilization <= 0.97;
        const attempt = { candidate, clientWidth, scrollWidth, clientHeight, scrollHeight, heightUtilization, fits: widthFits && heightFits && safeHeight };
        attempts.push(attempt);
        if (attempt.fits) {
            selected = attempt;
            break;
        }
    }
    const finalAttempt = selected || attempts[attempts.length - 1];
    const result = selected ? 'fit' : 'overflow';
    finish(result, {
        browserSelectedId: finalAttempt.candidate.id,
        browserSelectedCharacterCount: finalAttempt.candidate.characterCount,
        attemptCount: attempts.length,
        clientWidth: finalAttempt.clientWidth,
        scrollWidth: finalAttempt.scrollWidth,
        clientHeight: finalAttempt.clientHeight,
        scrollHeight: finalAttempt.scrollHeight,
        heightUtilization: finalAttempt.heightUtilization,
        attempts: JSON.stringify(attempts.map(attempt => ({ id: attempt.candidate.id, fits: attempt.fits, clientWidth: attempt.clientWidth, scrollWidth: attempt.scrollWidth, clientHeight: attempt.clientHeight, scrollHeight: attempt.scrollHeight, heightUtilization: attempt.heightUtilization }))),
    });
}

async function fitArrivalArticle() {
    const TARGET_FILL_RATIO = 0.94;
    const MAX_FILL_RATIO = 0.97;
    const container = document.querySelector('[data-arrival-fit-container]');
    if (container && container.hasAttribute('data-birth-story')) {
        if (document.fonts && document.fonts.ready) await document.fonts.ready;
        await new Promise(requestAnimationFrame);
        const story = container.querySelector('.arrival-story');
        const availableHeight = story ? story.clientHeight : 0;
        const contentHeight = story ? story.scrollHeight : 0;
        container.dataset.arrivalFitResult = 'birth-story-fit';
        container.dataset.arrivalMeasuredFill = availableHeight ? contentHeight / availableHeight : 1;
        await fitPresidentContext(container);
        container.classList.remove('arrival-fit-pending');
        return;
    }
    const data = document.querySelector('[data-arrival-candidates]');
    if (!container || !data) return;

    let candidates;
    try {
        candidates = JSON.parse(data.textContent);
    } catch (error) {
        return;
    }
    if (!Array.isArray(candidates) || !candidates.length) return;

    const headline = container.querySelector('[data-arrival-headline]');
    const wish = container.querySelector('[data-arrival-president-wish]');
    const body = container.querySelector('[data-arrival-body]');
    const content = container.querySelector('.arrival-content');
    const text = container.querySelector('.arrival-text');
    const paddingBottom = parseFloat(getComputedStyle(container).paddingBottom) || 0;
    const fixedArticleBottom = container.getBoundingClientRect().bottom;
    const measure = () => {
        const availableHeight = Math.max(0, fixedArticleBottom - content.getBoundingClientRect().top - paddingBottom);
        const contentHeight = text.scrollHeight;
        return {
            availableHeight,
            contentHeight,
            fillRatio: availableHeight ? contentHeight / availableHeight : 1,
            overflow: contentHeight > availableHeight,
        };
    };
    const attempts = [];
    const apply = (candidate, fontMode) => {
        headline.textContent = candidate.headline;
        if (wish) wish.textContent = candidate.presidentWishText;
        body.textContent = candidate.bodyText;
        container.classList.remove('arrival-fit--normal', 'arrival-fit--compact', 'arrival-fit--tight');
        container.classList.add(`arrival-fit--${fontMode}`);
        container.dataset.arrivalTemplateId = candidate.id;
        container.dataset.arrivalLengthClass = candidate.lengthClass;
        void container.offsetHeight;
    };

    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await new Promise(requestAnimationFrame);
    const measurements = [];
    const ranks = { extended: 0, expanded: 1, standard: 2, medium: 3, compact: 4, ultra_compact: 5 };
    const remaining = candidates.slice(1);
    let candidate = candidates[0];
    for (let attempt = 0; attempt < 3 && candidate; attempt += 1) {
        apply(candidate, 'normal');
        const measurement = {
            id: candidate.id,
            clientHeight: container.clientHeight,
            ...measure(),
        };
        attempts.push(measurement);
        measurements.push({ candidate, measurement });
        if (measurement.fillRatio >= 0.88 && measurement.fillRatio <= MAX_FILL_RATIO) break;
        const currentRank = ranks[candidate.lengthClass] ?? 2;
        const direction = measurement.fillRatio > MAX_FILL_RATIO ? 1 : -1;
        candidate = remaining
            .filter(item => direction > 0 ? (ranks[item.lengthClass] ?? 2) > currentRank : (ranks[item.lengthClass] ?? 2) < currentRank)
            .sort((left, right) => Math.abs((ranks[left.lengthClass] ?? 2) - currentRank) - Math.abs((ranks[right.lengthClass] ?? 2) - currentRank))[0];
        if (candidate) remaining.splice(remaining.indexOf(candidate), 1);
    }
    const valid = measurements.filter(({ measurement }) => measurement.fillRatio <= MAX_FILL_RATIO);
    const best = valid.sort((left, right) => {
        const distance = item => Math.abs(item.measurement.fillRatio - TARGET_FILL_RATIO);
        return distance(left) - distance(right) || right.measurement.fillRatio - left.measurement.fillRatio;
    })[0];
    if (best) {
        apply(best.candidate, 'normal');
        container.dataset.arrivalFitAttempts = JSON.stringify(attempts);
        container.dataset.arrivalMeasuredFill = best.measurement.fillRatio;
        container.dataset.arrivalFitResult = 'fit-target';
        container.classList.remove('arrival-fit-pending');
        return;
    }
    const shortest = measurements.find(({ candidate }) => candidate.lengthClass === 'ultra_compact')?.candidate || candidates[candidates.length - 1];
    apply(shortest, 'compact');
    attempts.push({ id: shortest.id, ...measure(), fontMode: 'compact' });
    if (!measure().overflow) {
        container.dataset.arrivalFitAttempts = JSON.stringify(attempts);
        container.dataset.arrivalMeasuredFill = measure().fillRatio;
        container.dataset.arrivalFitResult = 'fit-compact';
        container.classList.remove('arrival-fit-pending');
        return;
    }
    apply(shortest, 'tight');
    attempts.push({ id: shortest.id, ...measure(), fontMode: 'tight' });
    container.dataset.arrivalFitAttempts = JSON.stringify(attempts);
    container.dataset.arrivalMeasuredFill = measure().fillRatio;
    container.dataset.arrivalFitResult = measure().overflow ? 'overflow' : 'fit-tight';
    container.classList.remove('arrival-fit-pending');
}

// Comma filter for Jinja
// This is registered as a Jinja filter, but for client-side use:
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

async function fitZodiacSection() {
    const TARGET_FILL = 0.93;
    const MAX_FILL = 0.97;
    const article = document.querySelector('[data-zodiac-fit-container]');
    const content = article && article.querySelector('[data-zodiac-fit-content]');
    const box = article && article.querySelector('[data-zodiac-image-box]');
    const image = box && box.querySelector('img');
    const data = document.querySelector('[data-zodiac-candidates]');
    const intro = article && article.querySelector('[data-zodiac-intro]');
    const fortune = article && article.querySelector('[data-zodiac-fortune]');
    const optional = article ? [...article.querySelectorAll('[data-zodiac-optional]')] : [];
    if (!article || !content || !box || !data || !intro || !fortune) return;

    let candidates;
    try {
        candidates = JSON.parse(data.textContent);
    } catch (error) {
        return;
    }
    if (!Array.isArray(candidates) || !candidates.length) return;
    article.classList.remove('zodiac-fit--tight');
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    if (image && !image.complete) await new Promise(resolve => {
        image.addEventListener('load', resolve, { once: true });
        image.addEventListener('error', resolve, { once: true });
    });
    if (image && image.naturalWidth && image.naturalHeight) {
        const ratio = image.naturalWidth / image.naturalHeight;
        const maxWidth = 175;
        const maxHeight = 150;
        const width = ratio >= 1 ? Math.min(maxWidth, maxHeight * ratio) : maxHeight * ratio;
        box.style.width = `${width}px`;
        box.style.height = `${width / ratio}px`;
        box.style.aspectRatio = `${ratio}`;
    }
    await new Promise(requestAnimationFrame);
    const bottom = article.getBoundingClientRect().bottom;
    const availableHeight = Math.max(0, bottom - content.getBoundingClientRect().top - (parseFloat(getComputedStyle(article).paddingBottom) || 0));
    const measure = () => ({ contentHeight: content.scrollHeight, fillRatio: availableHeight ? content.scrollHeight / availableHeight : 1 });
    const attempts = [];
    let best = null;
    for (const candidate of candidates) {
        intro.textContent = candidate.introText;
        fortune.textContent = candidate.fortuneText;
        optional.forEach(item => { item.style.display = 'none'; });
        void content.offsetHeight;
        const result = measure();
        attempts.push({ id: candidate.id, ...result, overflow: result.fillRatio > MAX_FILL });
        if (result.fillRatio <= MAX_FILL && (!best || Math.abs(result.fillRatio - TARGET_FILL) < Math.abs(best.fillRatio - TARGET_FILL))) {
            best = { candidate, ...result, optionalCount: 0 };
        }
    }
    if (!best) {
        article.classList.add('zodiac-fit--tight');
        best = { candidate: candidates[candidates.length - 1], ...measure(), optionalCount: 0 };
    }
    intro.textContent = best.candidate.introText;
    fortune.textContent = best.candidate.fortuneText;
    for (let count = 0; count <= optional.length; count += 1) {
        optional.forEach((item, index) => { item.style.display = index < count ? '' : 'none'; });
        void content.offsetHeight;
        const result = measure();
        if (result.fillRatio <= MAX_FILL && Math.abs(result.fillRatio - TARGET_FILL) < Math.abs(best.fillRatio - TARGET_FILL)) {
            best = { candidate: best.candidate, ...result, optionalCount: count };
        }
    }
    optional.forEach((item, index) => { item.style.display = index < best.optionalCount ? '' : 'none'; });
    article.dataset.zodiacFit = JSON.stringify({ availableHeight, contentHeight: best.contentHeight, fillRatio: best.fillRatio, templateId: best.candidate.id, optionalCount: best.optionalCount, attempts });
    article.classList.remove('zodiac-fit-pending');
}

async function fitWeatherCopy() {
    const weather = document.querySelector('[data-weather-component]');
    const summary = weather && weather.querySelector('[data-weather-summary]');
    if (!weather || !summary) return;

    let copy;
    try {
        const response = await fetch('/dev/weather-copy-templates');
        copy = await response.json();
    } catch (error) {
        copy = {};
    }

    if (document.fonts && document.fonts.ready) await document.fonts.ready;

    const image = weather.querySelector('img');
    if (image && !image.complete) {
        await new Promise(resolve => {
            image.addEventListener('load', resolve, { once: true });
            image.addEventListener('error', resolve, { once: true });
        });
    }

    await new Promise(requestAnimationFrame);

    const key = (weather.dataset.weatherCondition || 'generic').toLowerCase().replace(/[- ]/g, '_');
    const character = (weather.dataset.weatherTemperatureCharacter || 'mild').toLowerCase();
    const copyKey = weather.dataset.weatherCopyKey || key;
    const candidates = (copy.fallbacks && copy.fallbacks[copyKey])
        || (copy.combinations && copy.combinations[key] && copy.combinations[key][character])
        || copy[key]
        || (copy.conditions && copy.conditions[key])
        || (copy.conditions && copy.conditions.generic)
        || copy.generic
        || {};
    const ordered = ['long', 'standard', 'compact'].map(length => ({
        length,
        text: candidates[length]
    })).filter(item => item.text);

    const date = weather.querySelector('.weather-date');
    let selected = null;

    for (const candidate of ordered.slice(0, 3)) {
        summary.textContent = candidate.text;
        void weather.offsetHeight;

        const fits = (
            weather.scrollWidth <= weather.clientWidth &&
            weather.scrollHeight <= weather.clientHeight &&
            summary.scrollHeight <= summary.clientHeight
        );

        // Also check that summary doesn't overlap date
        const summaryRect = summary.getBoundingClientRect();
        const dateRect = date.getBoundingClientRect();
        const noOverlap = summaryRect.bottom <= dateRect.top + 1;

        if (fits && noOverlap) {
            selected = candidate;
            break;
        }
    }

    // If nothing fits, use compact as fallback (it should always fit)
    if (!selected && ordered.length) {
        selected = ordered[ordered.length - 1];
        summary.textContent = selected.text;
    }

    // Store fit metadata for debugging
    weather.dataset.weatherCopyFit = JSON.stringify({
        selected: selected ? selected.length : 'none',
        overflow: weather.scrollHeight > weather.clientHeight
    });

    weather.classList.remove('weather-fit-pending');
    checkWeatherDimensions();
}