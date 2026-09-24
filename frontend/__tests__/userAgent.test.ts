import { describeUserAgent } from "../app/lib/userAgent";

const IPHONE_SAFARI =
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1";
const IPHONE_CHROME =
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/126.0.6478.54 Mobile/15E148 Safari/604.1";
const ANDROID_CHROME =
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36";
const WINDOWS_EDGE =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.2592.68";
const MAC_FIREFOX = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:127.0) Gecko/20100101 Firefox/127.0";
const LINUX_CHROME =
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";

test.each([
    [IPHONE_SAFARI, "Safari", "iOS"],
    // iOS agents say "like Mac OS X" and Chrome on iOS says CriOS, not Chrome.
    [IPHONE_CHROME, "Chrome", "iOS"],
    // Android agents also say "Linux".
    [ANDROID_CHROME, "Chrome", "Android"],
    // Edge also announces Chrome and Safari.
    [WINDOWS_EDGE, "Edge", "Windows"],
    [MAC_FIREFOX, "Firefox", "macOS"],
    [LINUX_CHROME, "Chrome", "Linux"],
    ["curl/8.5.0", "curl", null],
    ["python-httpx/0.27.0", "Python", null],
])("%s → %s on %s", (ua, browser, os) => {
    expect(describeUserAgent(ua)).toEqual({ browser, os });
});

test("a missing agent describes nothing rather than guessing", () => {
    expect(describeUserAgent(null)).toEqual({ browser: null, os: null });
    expect(describeUserAgent("")).toEqual({ browser: null, os: null });
});
