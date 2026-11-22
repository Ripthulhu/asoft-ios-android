package com.asoft.ios;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class SetupOwnerTest {
    @Test
    public void theSetupsQemuIsOwnedWhileItRuns() {
        assertTrue(SetupOwner.owns(4242, 4242, true));
    }

    @Test
    public void aLaterQemuOfTheUsersIsNeverOwned() {
        // the setup's QEMU ended, the user started iOS: another pid
        assertFalse(SetupOwner.owns(4242, 5151, true));
    }

    @Test
    public void aQemuThatIsGoneOwnsNothing() {
        assertFalse(SetupOwner.owns(4242, 4242, false));
    }

    @Test
    public void noSetupAtAllOwnsNothing() {
        assertFalse(SetupOwner.owns(-1, -1, true));
        assertFalse(SetupOwner.owns(-1, 4242, true));
        assertFalse(SetupOwner.owns(0, 0, true));
        assertFalse(SetupOwner.owns(4242, -1, true));
    }
}
