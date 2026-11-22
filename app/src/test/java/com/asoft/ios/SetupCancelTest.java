package com.asoft.ios;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotSame;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertSame;

import java.io.File;
import org.junit.Test;

/**
 * Which work folder a Cancel of a stopped setup deletes. A fresh process (Android killed the app while an iOS 26 /
 * watchOS setup was stopped) has State.target "ios16", so a Cancel that did not name its target deleted iOS 16's work
 * and left the iOS 26 setup's.
 */
public class SetupCancelTest {
    private static final File IOS16 = new File("setup/ios16");
    private static final File A26 = new File("setup/a26");

    private static File cancelled(String named, String last) {
        return SetupCancel.work(SetupCancel.target(named, last), IOS16, A26);
    }

    @Test
    public void theTargetsAreTheWordsTheStartIntentsUse() {
        assertEquals("ios16", SetupCancel.IOS16);
        assertEquals("a26", SetupCancel.A26);
        assertNotSame(IOS16, A26);
    }

    @Test
    public void eachTargetsCancelDeletesItsOwnWorkFolder() {
        assertSame(IOS16, SetupCancel.work("ios16", IOS16, A26));
        assertSame(A26, SetupCancel.work("a26", IOS16, A26));
    }

    @Test
    public void aTargetThatIsNeitherDeletesNothing() {
        assertNull(SetupCancel.work(null, IOS16, A26));
        assertNull(SetupCancel.work("", IOS16, A26));
        assertNull(SetupCancel.work("hosted27", IOS16, A26));
    }

    @Test
    public void aFreshProcessCancelOfIos26DeletesIos26sFolderNotIos16s() {
        // the bug: the service's last target is the default "ios16" in a fresh process, the screen's Cancel is for iOS 26
        assertSame(A26, cancelled("a26", "ios16"));
        // the mirror: the service ran iOS 26 last, the iOS 16 screen's Cancel is for iOS 16
        assertSame(IOS16, cancelled("ios16", "a26"));
    }

    @Test
    public void theNamedTargetWinsWhateverTheServiceRanLast() {
        for (String last : new String[] {"ios16", "a26", "hosted27", null}) {
            assertSame("last " + last, IOS16, cancelled("ios16", last));
            assertSame("last " + last, A26, cancelled("a26", last));
        }
    }

    @Test
    public void aCancelThatNamesNothingIsForTheTargetTheServiceRanLast() {
        // the running service's own notification Cancel: it knows its target
        assertEquals("a26", SetupCancel.target(null, "a26"));
        assertEquals("ios16", SetupCancel.target(null, "ios16"));
        assertSame(A26, cancelled(null, "a26"));
        assertSame(IOS16, cancelled(null, "ios16"));
    }
}
