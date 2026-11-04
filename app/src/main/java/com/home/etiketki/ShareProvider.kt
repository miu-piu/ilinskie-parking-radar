package com.home.etiketki

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.net.Uri
import android.os.ParcelFileDescriptor
import java.io.File

class ShareProvider:ContentProvider(){
 override fun onCreate()=true
 override fun getType(uri:Uri)="application/pdf"
 override fun query(uri:Uri,projection:Array<out String>?,selection:String?,selectionArgs:Array<out String>?,sortOrder:String?):Cursor?=null
 override fun insert(uri:Uri,values:ContentValues?):Uri?=null
 override fun delete(uri:Uri,selection:String?,selectionArgs:Array<out String>?):Int=0
 override fun update(uri:Uri,values:ContentValues?,selection:String?,selectionArgs:Array<out String>?):Int=0
 override fun openFile(uri:Uri,mode:String):ParcelFileDescriptor{
  if(uri.path!="/etiketki.pdf"||mode!="r")throw java.io.FileNotFoundException()
  return ParcelFileDescriptor.open(File(context!!.cacheDir,"shared/etiketki.pdf"),ParcelFileDescriptor.MODE_READ_ONLY)
 }
}
