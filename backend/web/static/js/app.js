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
    fitFamousBirthdays();
    fitAroundThisTime();
    fitZodiacSection();
    fitMoviesSection();
    fitMusicSection();
    fitWeatherCopy();
    window.addEventListener('resize', function () {
        const events = document.querySelector('[data-around-events]');
        if (events) autoFitEvents(events);
    });
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
    const articles = [...document.querySelectorAll('.chronicle-music')];
    if (!articles.length) return;
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await Promise.all(articles.map(async article => {
        const list = article.querySelector('.music-songs-list');
        if (!list) return;

        const image = article.querySelector('img');
        if (image && !image.complete) {
            await new Promise(resolve => {
                image.addEventListener('load', resolve, { once: true });
                image.addEventListener('error', resolve, { once: true });
            });
        }
        await new Promise(requestAnimationFrame);

        const styles = getComputedStyle(article);
        const paddingTop = parseFloat(styles.paddingTop) || 0;
        const paddingRight = parseFloat(styles.paddingRight) || 0;
        const paddingBottom = parseFloat(styles.paddingBottom) || 0;
        const tracks = [...article.querySelectorAll('[data-music-track]')];
        const art = article.querySelector('.music-art');
        const candidateCount = tracks.length;
        const fontSize = parseFloat(getComputedStyle(list).fontSize);
        const measure = () => {
            const root = article.getBoundingClientRect();
            const usableRight = root.left + article.clientWidth;
            const usableBottom = root.top + article.clientHeight - paddingBottom;
            const visibleTracks = tracks.filter(track => !track.hidden);
            const last = visibleTracks[visibleTracks.length - 1];
            const lastRect = last?.getBoundingClientRect();
            const artRect = art?.querySelector('img')?.getBoundingClientRect();
            const trackOverlap = artRect && visibleTracks.some(track => {
                const trackRect = track.getBoundingClientRect();
                return trackRect.right > artRect.left && trackRect.left < artRect.right && trackRect.bottom > artRect.top && trackRect.top < artRect.bottom;
            });
            const tracksFit = !lastRect || lastRect.bottom <= usableBottom + 0.5;
            const artFit = !artRect || (artRect.top >= root.top + paddingTop + 6 && artRect.right <= usableRight + 0.5 && artRect.bottom <= usableBottom + 0.5);
            return {
                visibleTracks,
                contentHeight: Math.max(0, (lastRect?.bottom || root.top + paddingTop) - (root.top + paddingTop)),
                availableHeight: Math.max(0, article.clientHeight - paddingTop - paddingBottom),
                tracksFit,
                artFit,
                trackOverlap: Boolean(trackOverlap),
                overflow: article.scrollWidth > article.clientWidth || article.scrollHeight > article.clientHeight,
                lastTrackBottom: lastRect ? lastRect.bottom - root.top : null,
                illustrationRight: artRect ? artRect.right - root.left : null,
                illustrationBottom: artRect ? artRect.bottom - root.top : null,
            };
        };
        tracks.forEach(track => { track.hidden = false; });
        void article.offsetHeight;
        const selected = measure();
        article.dataset.musicFit = JSON.stringify({
            candidateCount,
            displayedCount: selected.visibleTracks.length,
            availableHeight: selected.availableHeight,
            contentHeight: selected.contentHeight,
            fontSize,
            rootClientWidth: article.clientWidth,
            rootScrollWidth: article.scrollWidth,
            rootClientHeight: article.clientHeight,
            rootScrollHeight: article.scrollHeight,
            lastTrackBottom: selected.lastTrackBottom,
            illustrationRight: selected.illustrationRight,
            illustrationBottom: selected.illustrationBottom,
            overlap: selected.trackOverlap,
            overflow: selected.overflow,
            fit: selected.tracksFit && selected.artFit && !selected.overflow,
        });
    }));
}

async function fitMoviesSection() {
    const article = document.querySelector('.chronicle-movies');
    const content = article && article.querySelector('[data-movies-fit-content]');
    const data = article && article.querySelector('[data-movie-candidates]');
    const list = article && article.querySelector('.movie-list');
    const items = list ? [...list.querySelectorAll('.movie-item[data-movie-item]')] : [];
    if (!article || !content || !data || !list) return;
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await new Promise(requestAnimationFrame);
    const candidates = JSON.parse(data.textContent);
    const baseFontSize = 10;
    const maxFontSize = 12.5;
    const lineHeight = 1.25;
    const maxHeight = list.clientHeight;
    let fontSize = baseFontSize;
    const applyFontSize = size => {
        list.style.fontSize = `${size}px`;
        items.forEach(item => {
            item.style.fontSize = `${size}px`;
            item.style.lineHeight = lineHeight;
        });
        void list.offsetHeight;
    };

    applyFontSize(fontSize);
    while (fontSize < maxFontSize && list.scrollHeight <= maxHeight) {
        fontSize += 0.5;
        applyFontSize(fontSize);
    }
    if (list.scrollHeight > maxHeight) {
        fontSize = Math.max(baseFontSize, fontSize - 0.5);
        applyFontSize(fontSize);
    }

    content.classList.remove('movies-fit-pending');
    article.dataset.movieFit = JSON.stringify({
        candidateCount: candidates.length,
        displayedCount: items.length,
        fontSize,
        clientHeight: maxHeight,
        scrollHeight: list.scrollHeight,
        fit: list.scrollHeight <= maxHeight,
    });
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
    const content = document.querySelector('[data-around-container]');
    const article = content && content.closest('[data-around-root]');
    const data = document.querySelector('[data-around-candidates]');
    const events = content && content.querySelector('[data-around-events]');
    const items = events && [...events.querySelectorAll('[data-around-item]')];
    if (!content || !article) return;
    if (!data || !events || !items?.length) {
        article.dataset.aroundFit = JSON.stringify({
            candidateCount: 0,
            displayedCount: 0,
            bodyClientWidth: content.clientWidth,
            bodyScrollWidth: content.scrollWidth,
            bodyClientHeight: content.clientHeight,
            bodyScrollHeight: content.scrollHeight,
            rootClientWidth: article.clientWidth,
            rootScrollWidth: article.scrollWidth,
            rootClientHeight: article.clientHeight,
            rootScrollHeight: article.scrollHeight,
            heightUtilization: content.clientHeight ? content.scrollHeight / content.clientHeight : 0,
            fitResult: 'empty',
            attempts: [],
        });
        content.classList.remove('around-fit-pending');
        return;
    }
    if (document.fonts && document.fonts.ready) {
        await Promise.race([
            document.fonts.ready,
            new Promise(resolve => window.setTimeout(resolve, 1500)),
        ]);
    }
    await Promise.race([
        new Promise(requestAnimationFrame),
        new Promise(resolve => window.setTimeout(resolve, 100)),
    ]);
    const candidates = JSON.parse(data.textContent);
    const availableHeight = content.clientHeight;
    const measure = () => ({
        bodyClientWidth: content.clientWidth,
        bodyScrollWidth: content.scrollWidth,
        bodyClientHeight: content.clientHeight,
        bodyScrollHeight: content.scrollHeight,
        naturalContentHeight: events.scrollHeight,
        naturalContentWidth: events.scrollWidth,
        rootClientWidth: article.clientWidth,
        rootScrollWidth: article.scrollWidth,
        rootClientHeight: article.clientHeight,
        rootScrollHeight: article.scrollHeight,
        fillRatio: availableHeight ? content.scrollHeight / availableHeight : 1,
    });
    const fits = result => {
        const visibleItems = items.filter(item => getComputedStyle(item).display !== 'none');
        const lastItem = visibleItems[visibleItems.length - 1];
        const rootRect = article.getBoundingClientRect();
        const lastItemRect = lastItem && lastItem.getBoundingClientRect();
        return result.bodyScrollHeight <= result.bodyClientHeight
            && result.bodyScrollWidth <= result.bodyClientWidth
            && result.rootScrollHeight <= result.rootClientHeight
            && result.rootScrollWidth <= result.rootClientWidth
            && !!lastItemRect
            && lastItemRect.bottom <= rootRect.bottom - 5;
    };
    const attempts = [];
    const render = (count, record = true) => {
        items.forEach((item, index) => { item.style.display = index < count ? '' : 'none'; });
        events.style.gap = count >= 5 ? '1px' : count === 4 ? '3px' : count === 3 ? '7px' : '9px';
        void content.offsetHeight;
        const result = measure();
        const fit = fits(result);
        if (record) attempts.push({ count, ...result, fit, overflow: !fit });
        return result;
    };
    let best = null;
    for (let count = Math.min(6, items.length, candidates.length); count >= Math.min(2, items.length, candidates.length); count -= 1) {
        const result = render(count);
        if (fits(result)) { best = { count, ...result }; break; }
    }
    if (!best) {
        const count = Math.min(1, items.length, candidates.length);
        best = { count, ...render(count) };
    }
    render(best.count, false);
    autoFitEvents(events);
    const final = measure();
    article.dataset.aroundFit = JSON.stringify({ candidateCount: candidates.length, displayedCount: best.count, availableHeight, ...final, heightUtilization: availableHeight ? final.naturalContentHeight / availableHeight : 0, fitResult: attempts.find(attempt => attempt.count === best.count)?.overflow ? 'overflow' : 'fit', attempts });
    content.classList.remove('around-fit-pending');
    if (!article.dataset.aroundResizeObserved && window.ResizeObserver) {
        let fitting = false;
        const observer = new ResizeObserver(() => {
            if (fitting) return;
            fitting = true;
            void fitAroundThisTime().finally(() => { fitting = false; });
        });
        observer.observe(article);
        article.dataset.aroundResizeObserved = 'true';
    }
}

function autoFitEvents(containerEl) {
    const maxHeight = containerEl.clientHeight;
    const items = [...containerEl.querySelectorAll('[data-around-item]')]
        .filter(item => getComputedStyle(item).display !== 'none');
    if (!maxHeight || !items.length) return;

    const targetHeight = maxHeight * 0.88;
    const baseFontSize = 11;
    const maxFontSize = 15;
    const getTextHeight = () => items.reduce((total, item) => total + item.getBoundingClientRect().height, 0);
    const fits = () => containerEl.scrollHeight <= maxHeight
        && containerEl.scrollWidth <= containerEl.clientWidth;

    containerEl.style.setProperty('--around-events-height', '88%');
    let fontSize = baseFontSize;
    containerEl.style.setProperty('--around-event-font-size', `${fontSize}px`);
    void containerEl.offsetHeight;

    while (fontSize < maxFontSize) {
        const nextFontSize = fontSize + 0.5;
        containerEl.style.setProperty('--around-event-font-size', `${nextFontSize}px`);
        void containerEl.offsetHeight;
        if (!fits()) break;
        fontSize = nextFontSize;
        if (getTextHeight() >= targetHeight) break;
    }

    containerEl.style.setProperty('--around-event-font-size', `${fontSize}px`);
    void containerEl.offsetHeight;
    if (!fits()) containerEl.style.setProperty('--around-event-font-size', `${Math.max(baseFontSize, fontSize - 0.5)}px`);
}

async function fitWorldNews() {
    const container = document.querySelector('[data-world-news-container]');
    const data = document.querySelector('[data-world-news-candidates]');
    const content = container && container.querySelector('[data-world-news-content]');
    const right = content && content.querySelector('.world-news-right');
    const list = right && right.querySelector('.world-news-list');
    const items = right && [...right.querySelectorAll('[data-world-news-item]')];
    if (!container || !data || !content || !right || !list) return;
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await new Promise(requestAnimationFrame);
    const candidates = JSON.parse(data.textContent);
    if (!items.length) {
        container.classList.remove('world-news-fit-pending');
        container.dataset.worldNewsFit = JSON.stringify({ candidateCount: candidates.length, displayCount: 0, fitResult: 'empty' });
        return;
    }
    const measure = () => ({
        clientWidth: content.clientWidth,
        scrollWidth: right.scrollWidth,
        clientHeight: content.clientHeight,
        scrollHeight: right.scrollHeight,
        briefsClientHeight: list.clientHeight,
        briefsScrollHeight: list.scrollHeight,
        fillRatio: content.clientHeight ? right.scrollHeight / content.clientHeight : 1,
    });
    const attempts = [];
    const render = count => {
        items.forEach((item, index) => { item.style.display = index < count ? '' : 'none'; });
        list.style.setProperty('--world-news-gap', '0px');
        void list.offsetHeight;
        const measurement = measure();
        attempts.push({ count, ...measurement, overflow: measurement.scrollHeight > measurement.clientHeight || measurement.scrollWidth > measurement.clientWidth });
        return measurement;
    };
    let best = null;
    for (let count = 1; count <= Math.min(candidates.length, items.length); count += 1) {
        const measurement = render(count);
        if (measurement.scrollHeight <= measurement.clientHeight && measurement.scrollWidth <= measurement.clientWidth) best = { count, measurement };
    }
    if (!best) best = { count: 1, measurement: render(1) };
    render(best.count);
    const briefCount = Math.max(0, best.count - 1);
    const natural = measure();
    const spareHeight = Math.max(0, content.clientHeight - natural.scrollHeight);
    const gap = briefCount > 1 ? Math.min(10, Math.max(2, spareHeight / (briefCount - 1))) : 0;
    list.style.setProperty('--world-news-gap', `${gap}px`);
    void list.offsetHeight;
    let finalMeasurement = measure();
    if (finalMeasurement.scrollHeight > content.clientHeight * 0.97) {
        list.style.setProperty('--world-news-gap', '2px');
        void list.offsetHeight;
        finalMeasurement = measure();
    }
    container.dataset.worldNewsFit = JSON.stringify({
        candidateCount: candidates.length,
        displayCount: best.count,
        ...finalMeasurement,
        fitResult: finalMeasurement.scrollHeight <= finalMeasurement.clientHeight && finalMeasurement.scrollWidth <= finalMeasurement.clientWidth ? 'fit' : 'overflow',
        attempts,
    });
    container.classList.remove('world-news-fit-pending');
}

async function fitPresidentContext(container) {
    const message = container.querySelector('[data-president-context-fit]');
    const flow = container.querySelector('[data-white-house-flow]') || message;
    const budgetBox = container.querySelector('[data-white-house-budget]') || flow;
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
    // Candidates arrive in a randomized attempt order (not ranked by length or
    // era); step through them as-is and fall back to neutral text if every
    // one overflows.
    const order = candidates;
    if (!order.length) {
        finish('no_candidates', { attemptCount: 0 });
        return;
    }
    if (container.dataset.presidentContextFitComplete === 'true') return;
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await new Promise(requestAnimationFrame);
    // The photo now floats inside the White House flow region, so the
    // available line width narrows near the top and widens once text passes
    // below the portrait. The flow region itself is auto-height (so its
    // scrollHeight reflects the candidate's true content extent); compare
    // that against the fixed budget box's clientHeight, which never changes.
    const budgetWidth = budgetBox.clientWidth;
    const budgetHeight = budgetBox.clientHeight;
    const attempts = [];
    let selected = null;
    for (const candidate of order) {
        message.textContent = candidate.text;
        await new Promise(requestAnimationFrame);
        const naturalWidth = flow.scrollWidth;
        const naturalHeight = flow.scrollHeight;
        const heightUtilization = budgetHeight > 0 ? naturalHeight / budgetHeight : null;
        const widthFits = naturalWidth <= budgetWidth + 1;
        const heightFits = naturalHeight <= budgetHeight + 1;
        const safeHeight = heightUtilization !== null && heightUtilization <= 0.97;
        const attempt = { candidate, clientWidth: budgetWidth, scrollWidth: naturalWidth, clientHeight: budgetHeight, scrollHeight: naturalHeight, heightUtilization, fits: widthFits && heightFits && safeHeight };
        attempts.push(attempt);
        if (attempt.fits) {
            selected = attempt;
            break;
        }
    }
    await new Promise(requestAnimationFrame);
    const finalAttempt = selected || attempts[attempts.length - 1];
    let result = selected ? 'fit' : 'overflow';
    let browserSelectedId = finalAttempt.candidate.id;
    let browserSelectedCharacterCount = finalAttempt.candidate.characterCount;
    if (!selected) {
        // Every wish-template candidate overflowed; drop to the neutral,
        // guaranteed-safe sentence rather than showing clipped/oversized text.
        const fallbackText = message.dataset.presidentContextFallbackText || '';
        message.textContent = fallbackText;
        await new Promise(requestAnimationFrame);
        result = 'fallback';
        browserSelectedId = 'fallback';
        browserSelectedCharacterCount = fallbackText.length;
    }
    finish(result, {
        browserSelectedId,
        browserSelectedCharacterCount,
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

async function fitFamousBirthdays() {
    const container = document.querySelector('[data-famous-birthdays-container]');
    const content = container && container.querySelector('[data-famous-birthdays-content]');
    const list = content && content.querySelector('[data-famous-birthdays-list]');
    const icons = content && content.querySelector('[data-famous-birthday-icons]');
    const items = list && [...list.querySelectorAll('[data-famous-birthday-person]')];
    if (!container || !content || !list || !items?.length) {
        container?.classList.remove('famous-birthdays-fit-pending');
        return;
    }
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await new Promise(requestAnimationFrame);
    const TOP_GAP = 6;
    const BOTTOM_SAFETY = 6;
    const measure = () => ({
        clientWidth: container.clientWidth,
        scrollWidth: container.scrollWidth,
        clientHeight: container.clientHeight,
        scrollHeight: container.scrollHeight,
    });
    let selected = items.length;
    for (let count = items.length; count >= 1; count -= 1) {
        items.forEach((item, index) => { item.style.display = index < count ? '' : 'none'; });
        void content.offsetHeight;
        const result = measure();
        if (result.scrollHeight <= result.clientHeight && result.scrollWidth <= result.clientWidth) {
            selected = count;
            break;
        }
    }
    items.forEach((item, index) => { item.style.display = index < selected ? '' : 'none'; });
    const result = measure();
    let iconMetrics = {
        normalContentBottom: 0,
        usableContainerBottom: 0,
        availableHeight: 0,
        iconRowHeight: 0,
        topGap: TOP_GAP,
        bottomSafety: BOTTOM_SAFETY,
        requiredHeight: 0,
        iconsAvailable: 0,
        shown: false,
        count: 0,
        occupations: [],
    };
    if (icons) {
        const iconImages = [...icons.querySelectorAll('[data-famous-birthday-icon]')];
        icons.hidden = true;
        iconImages.forEach(image => { image.hidden = Number(image.dataset.personIndex) >= selected; });
        const displayedIcons = iconImages.filter(image => !image.hidden);
        const lastNormal = content.querySelector('.famous-birthday-days') || list;
        const containerRect = container.getBoundingClientRect();
        const contentStyle = getComputedStyle(content);
        const bottomPadding = parseFloat(contentStyle.paddingBottom) || 0;
        const normalBottom = lastNormal.getBoundingClientRect().bottom;
        const usableContainerBottom = containerRect.bottom - bottomPadding;
        const availableHeight = Math.max(0, usableContainerBottom - normalBottom);
        iconMetrics = {
            normalContentBottom: normalBottom,
            usableContainerBottom,
            availableHeight,
            iconRowHeight: 0,
            topGap: TOP_GAP,
            bottomSafety: BOTTOM_SAFETY,
            requiredHeight: 0,
            iconsAvailable: displayedIcons.length,
            shown: false,
            count: 0,
            occupations: [],
        };
        if (displayedIcons.length) {
            icons.style.marginTop = `${TOP_GAP}px`;
            icons.hidden = false;
            icons.style.visibility = 'hidden';
            void icons.offsetHeight;
            const iconImage = displayedIcons[0];
            const iconRowHeight = iconImage.getBoundingClientRect().height;
            const requiredHeight = TOP_GAP + iconRowHeight + BOTTOM_SAFETY;
            iconMetrics.iconRowHeight = iconRowHeight;
            iconMetrics.requiredHeight = requiredHeight;
            const actualNormalBottom = lastNormal.getBoundingClientRect().bottom;
            const actualAvailableHeight = Math.max(0, usableContainerBottom - actualNormalBottom);
            const measuredIconRect = iconImage.getBoundingClientRect();
            iconMetrics.normalContentBottom = actualNormalBottom;
            iconMetrics.availableHeight = actualAvailableHeight;
            if (actualAvailableHeight >= requiredHeight
                && measuredIconRect.top >= actualNormalBottom + TOP_GAP - 0.5
                && measuredIconRect.bottom <= usableContainerBottom - BOTTOM_SAFETY + 0.5) {
                icons.style.visibility = '';
                void icons.offsetHeight;
                const iconRect = icons.getBoundingClientRect();
                const finalResult = measure();
                const finalUsableBottom = container.getBoundingClientRect().bottom - bottomPadding;
                const fits = container.scrollHeight <= container.clientHeight
                    && container.scrollWidth <= container.clientWidth
                    && iconRect.bottom <= finalUsableBottom - BOTTOM_SAFETY + 0.5
                    && iconRect.top >= normalBottom + TOP_GAP - 0.5;
                if (fits) {
                    iconMetrics.shown = true;
                    iconMetrics.count = displayedIcons.length;
                    iconMetrics.occupations = displayedIcons.map(image => image.dataset.occupation);
                } else {
                    icons.hidden = true;
                }
            } else {
                icons.hidden = true;
            }
        }
    }
    const finalResult = measure();
    container.dataset.famousBirthdaysFit = JSON.stringify({
        candidateCount: items.length,
        displayCount: selected,
        ...finalResult,
        ...iconMetrics,
        fitResult: container.scrollHeight <= container.clientHeight && container.scrollWidth <= container.clientWidth ? 'fit' : 'overflow',
    });
    container.classList.remove('famous-birthdays-fit-pending');
}