package com.home.etiketki

import org.junit.Assert.*
import org.junit.Test

class LabelLogicTest {
    @Test fun pageCounts() {
        val expected = listOf(0,1,1,1,2,2,2,3)
        expected.forEachIndexed { count, sheets ->
            assertEquals("count=$count", sheets, LabelLogic.sheetCount(count))
        }
    }
    @Test fun paginationKeepsOrderAndPartialPage() {
        val pages = LabelLogic.pages((1..8).toList())
        assertEquals(listOf(listOf(1,2,3),listOf(4,5,6),listOf(7,8)),pages)
        assertTrue(LabelLogic.pages(emptyList<Int>()).isEmpty())
    }
    @Test fun geometryMatchesThreeLabels() {
        assertEquals(960, LabelLogic.LABEL_HEIGHT_DOTS * LabelLogic.LABELS_PER_PAGE)
        assertEquals(75, LabelLogic.rowBytes(LabelLogic.WIDTH_DOTS))
    }
    @Test fun bitmapPacksBitsInPrinterOrder() {
        val bits = ByteArray(4)
        LabelLogic.setBlackPixel(bits,16,0,0)
        LabelLogic.setBlackPixel(bits,16,7,0)
        LabelLogic.setBlackPixel(bits,16,8,0)
        LabelLogic.setBlackPixel(bits,16,15,1)
        assertEquals(0x81, bits[0].toInt() and 255)
        assertEquals(0x80, bits[1].toInt() and 255)
        assertEquals(0, bits[2].toInt() and 255)
        assertEquals(0x01, bits[3].toInt() and 255)
    }
    @Test(expected=IllegalArgumentException::class)
    fun rejectsNegativeCounts() { LabelLogic.sheetCount(-1) }
}
