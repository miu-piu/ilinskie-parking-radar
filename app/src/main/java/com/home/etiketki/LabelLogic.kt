package com.home.etiketki

object LabelLogic {
    const val LABELS_PER_PAGE = 3
    const val WIDTH_DOTS = 600
    const val HEIGHT_DOTS = 960
    const val LABEL_HEIGHT_DOTS = 320

    fun <T> pages(labels: List<T>): List<List<T>> = labels.chunked(LABELS_PER_PAGE)
    fun sheetCount(labelCount: Int): Int {
        require(labelCount >= 0)
        return (labelCount + LABELS_PER_PAGE - 1) / LABELS_PER_PAGE
    }
    fun rowBytes(width: Int): Int {
        require(width > 0)
        return (width + 7) / 8
    }
    fun setBlackPixel(bytes: ByteArray, width: Int, x: Int, y: Int) {
        require(width > 0 && x in 0 until width && y >= 0)
        val index = y * rowBytes(width) + x / 8
        require(index in bytes.indices)
        bytes[index] = (bytes[index].toInt() or (0x80 ushr (x % 8))).toByte()
    }
}
