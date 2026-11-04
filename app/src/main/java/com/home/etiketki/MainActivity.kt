package com.home.etiketki

import android.app.*
import android.os.Bundle
import android.content.*
import android.graphics.*
import android.graphics.pdf.PdfDocument
import android.net.Uri
import android.text.*
import android.view.*
import android.widget.*
import java.io.File
import java.util.Locale

class MainActivity:Activity(){
 data class Label(val title:String,val detail:String="")
 private val sections=linkedMapOf(
 "Кухня" to "Бакалея|Крупы|Макароны|Семена|Крупы и макароны|Макароны · Крупы · Семена|Рис|Гречка|Овсянка|Бобовые|Мука|Сахар|Соль|Специи|Приправы|Масла|Соусы|Чай|Кофе|Какао|Завтраки|Снеки|Сладости|Орехи|Сухофрукты|Консервы|Запасы|Выпечка|Для выпечки|Кондитерские принадлежности|Контейнеры|Крышки|Посуда|Столовые приборы|Кухонный текстиль|Пакеты|Фольга и плёнка|Хранение продуктов",
 "Одежда" to "Женская одежда|Мужская одежда|Детская одежда|Верхняя одежда|Повседневная одежда|Праздничная одежда|Спортивная одежда|Домашняя одежда|Летняя одежда|Зимняя одежда|Демисезонная одежда|Нижнее бельё|Носки|Колготки|Футболки|Рубашки|Брюки|Джинсы|Платья|Юбки|Свитеры|Толстовки|Куртки|Пальто|Шапки|Шарфы|Перчатки|Шапки · Шарфы · Перчатки|Сумки|Ремни|Аксессуары|На вырост|Мало|Велико|Отдать|Продать|На хранение",
 "Детское" to "Игрушки|Мягкие игрушки|Конструкторы|Кубики|Машинки|Куклы|Книги|Развивающие игры|Настольные игры|Творчество|Краски|Карандаши|Бумага|Лепка|Пазлы|Прогулки|Подгузники|Гигиена|Детская обувь|Детская одежда|Боди|Слипы|Пижамы|Комбинезоны|Размер 74|Размер 80|Размер 86|Размер 92|Размер 98|Размер 104|На вырост|Мало|Велико|Зима|Лето|Весна · Осень",
 "Хозяйство" to "Уборка|Бытовая химия|Чистящие средства|Губки|Тряпки|Салфетки|Перчатки|Стирка|Средства для стирки|Порошки|Кондиционеры|Мешки для стирки|Пакеты для мусора|Расходники|Запас|Лампочки|Батарейки|Аккумуляторы|Инструменты|Отвёртки|Ключи|Крепёж|Винты · Гайки · Шайбы|Клей|Скотч|Ремонт|Сантехника|Электрика|Сад|Растения",
 "Техника" to "Кабели|Зарядки|Адаптеры|Кабели · Зарядки · Адаптеры|USB-C|HDMI|Переходники|Блоки питания|Компьютеры|Мыши|Клавиатуры|Наушники|Телефоны|Чехлы|Защитные стёкла|Флешки|Карты памяти|Умный дом|Датчики|Пульты|Запчасти",
 "Ванная" to "Косметика|Уход за лицом|Уход за телом|Уход за волосами|Шампуни|Маски|Кремы|Сыворотки|Средства для душа|Гигиена|Зубные щётки|Зубная паста|Полотенца|Аптечка|Перевязочные материалы|Лекарства|Витамины|Запас косметики",
 "Документы" to "Документы|Договоры|Справки|Свидетельства|Гарантии|Чеки|Инструкции|Квитанции|Налоги|Страхование|Автомобиль|Недвижимость|Работа|Финансы|Архив|Канцелярия|Бумага|Конверты|Блокноты|Ручки",
 "Сезонное" to "Новый год|Ёлочные игрушки|Гирлянды|Украшения|Праздники|Декор|Свечи|Подарки|Упаковка подарков|Открытки|Путешествия|Чемоданы|Дорожные принадлежности|Пикник|Отдых|Спорт|Хобби|Шитьё|Нитки|Иглы|Фото|Альбомы|Собака|Товары для животных"
 )
 private val queue=mutableListOf<Label>()
 private val picked=linkedSetOf<String>()
 private lateinit var list:LinearLayout
 private lateinit var search:EditText
 private lateinit var footer:TextView
 private var section="Все"
 private val bg=Color.rgb(248,247,243)
 private val ink=Color.rgb(39,47,43)
 private val sage=Color.rgb(92,112,98)
 override fun onCreate(savedInstanceState:Bundle?){super.onCreate(savedInstanceState);window.statusBarColor=bg;window.navigationBarColor=bg;window.decorView.systemUiVisibility=View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;home()}
 private fun dp(n:Int)=(n*resources.displayMetrics.density).toInt()
 private fun txt(s:String,size:Float=16f,bold:Boolean=false)=TextView(this).apply{text=s;textSize=size;setTextColor(ink);if(bold)setTypeface(null,1);setPadding(dp(8),dp(9),dp(8),dp(9))}
 private fun btn(s:String,action:()->Unit)=Button(this).apply{text=s;isAllCaps=false;textSize=13f;setTextColor(Color.WHITE);backgroundTintList=android.content.res.ColorStateList.valueOf(sage);setOnClickListener{action()}}
 private fun base(title:String):LinearLayout{
  val root=LinearLayout(this).apply{orientation=1;setBackgroundColor(bg);setPadding(dp(12),dp(12),dp(12),dp(12))}
  setContentView(root);root.addView(txt(title,25f,true))
  return root
 }
 private fun home(){
  val root=base("По полочкам")
  search=EditText(this).apply{hint="Найти или создать наклейку";setSingleLine(true);textSize=16f}
  root.addView(search)
  val chips=HorizontalScrollView(this);val row=LinearLayout(this).apply{orientation=0}
  (listOf("Все")+sections.keys).forEach{cat->row.addView(btn(cat){section=cat;render()})}
  chips.addView(row);root.addView(chips)
  val scroll=ScrollView(this);list=LinearLayout(this).apply{orientation=1};scroll.addView(list);root.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
  footer=txt("",14f);root.addView(footer)
  root.addView(btn("Выбранные → объединить в одну"){combine()})
  root.addView(btn("Очередь и печать"){printScreen()})
  search.addTextChangedListener(object:TextWatcher{
   override fun beforeTextChanged(s:CharSequence?,start:Int,count:Int,after:Int){}
   override fun onTextChanged(s:CharSequence?,start:Int,before:Int,count:Int){render()}
   override fun afterTextChanged(s:Editable?){}
  })
  render()
 }
 private fun all()=sections.flatMap{(cat,str)->str.split("|").map{cat to it}}.distinctBy{it.second.lowercase(Locale.ROOT)}
 private fun render(){
  list.removeAllViews();val q=search.text.toString().trim()
  val found=all().filter{(cat,name)->(section=="Все"||section==cat)&&(q.isBlank()||name.contains(q,true)||cat.contains(q,true))}
  found.take(180).forEach{(cat,name)->
   val line=LinearLayout(this).apply{orientation=0;gravity=Gravity.CENTER_VERTICAL}
   val check=CheckBox(this).apply{isChecked=name in picked;setOnCheckedChangeListener{_,yes->if(yes)picked.add(name) else picked.remove(name);updateFooter()}}
   line.addView(check)
   val label=txt(name,16f,true);line.addView(label,LinearLayout.LayoutParams(0,-2,1f))
   line.addView(btn("+"){edit(name,"")})
   list.addView(line)
  }
  if(q.isNotBlank()&&found.none{it.second.equals(q,true)})list.addView(btn("Создать «$q»"){edit(q,"")})
  if(found.size>180)list.addView(txt("Уточни поиск, чтобы увидеть остальные варианты",13f))
  updateFooter()
 }
 private fun updateFooter(){footer.text="Выбрано для объединения: ${picked.size}    ·    В очереди: ${queue.size}"}
 private fun combine(){
  if(picked.isEmpty()){Toast.makeText(this,"Отметь названия галочками",0).show();return}
  edit(picked.joinToString(" · "),"")
 }
 private fun edit(name:String,detail:String){
  val box=LinearLayout(this).apply{orientation=1;setPadding(dp(20),0,dp(20),0)}
  val title=EditText(this).apply{setText(name);hint="Название"}
  val sub=EditText(this).apply{setText(detail);hint="Уточнение (необязательно)"}
  box.addView(title);box.addView(sub)
  AlertDialog.Builder(this).setTitle("Наклейка").setView(box).setNegativeButton("Отмена",null)
   .setPositiveButton("В очередь"){_,_->val s=title.text.toString().trim();if(s.isNotEmpty()){queue.add(Label(s,sub.text.toString().trim()));picked.clear();updateFooter()}}.show()
 }
 private fun printScreen(){
  val root=base("Печать")
  root.addView(txt("75 × 120 мм · 3 наклейки на лист",14f))
  val scroll=ScrollView(this);val content=LinearLayout(this).apply{orientation=1};scroll.addView(content)
  root.addView(scroll,LinearLayout.LayoutParams(-1,0,1f))
  fun redraw(){
   content.removeAllViews()
   queue.forEachIndexed{i,l->
    val row=LinearLayout(this).apply{orientation=0;gravity=Gravity.CENTER_VERTICAL}
    row.addView(txt("${i+1}. ${l.title}",14f),LinearLayout.LayoutParams(0,-2,1f))
    row.addView(btn("×"){queue.removeAt(i);redraw()})
    content.addView(row)
   }
   if(queue.isEmpty())content.addView(txt("Очередь пуста. Выбери готовые наклейки.",15f))
   content.addView(txt("Листов: ${LabelLogic.sheetCount(queue.size)}",15f,true))
  }
  redraw()
  root.addView(btn("Открыть PDF для печати"){exportPdf()})
  root.addView(btn("Добавить наклейки"){home()})
 }
 private fun exportPdf(){
  if(queue.isEmpty()){Toast.makeText(this,"Очередь пуста",0).show();return}
  try{
   val pdf=PdfDocument()
   queue.chunked(3).forEachIndexed{index,labels->
    val page=pdf.startPage(PdfDocument.PageInfo.Builder(213,340,index+1).create())
    val c=page.canvas;c.drawColor(Color.WHITE)
    labels.forEachIndexed{slot,l->
     val top=slot*113f
     val p=Paint(Paint.ANTI_ALIAS_FLAG).apply{color=Color.BLACK;typeface=Typeface.DEFAULT_BOLD}
     c.drawLine(8f,top+7f,205f,top+7f,p)
     drawFit(c,p,l.title,10f,top+52f,194f,18f)
     if(l.detail.isNotBlank()){p.typeface=Typeface.DEFAULT;drawFit(c,p,l.detail,10f,top+80f,194f,11f)}
    }
    pdf.finishPage(page)
   }
   val dir=File(cacheDir,"shared");dir.mkdirs();val file=File(dir,"etiketki.pdf")
   file.outputStream().use{pdf.writeTo(it)};pdf.close()
   val uri=Uri.parse("content://"+packageName+".share/etiketki.pdf")
   val intent=Intent(Intent.ACTION_SEND).apply{type="application/pdf";putExtra(Intent.EXTRA_STREAM,uri);addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);clipData=ClipData.newUri(contentResolver,"Наклейки",uri)}
   startActivity(Intent.createChooser(intent,"Передать PDF в Label Expert или другое приложение"))
  }catch(e:Exception){AlertDialog.Builder(this).setMessage("Не удалось передать PDF: "+e.message).setPositiveButton("ОК",null).show()}
 }
 private fun drawFit(c:Canvas,p:Paint,s:String,x:Float,y:Float,width:Float,size:Float){
  p.textSize=size;while(p.measureText(s)>width&&p.textSize>8f)p.textSize-=0.5f
  if(p.measureText(s)<=width){c.drawText(s,x,y,p);return}
  val words=s.split(" ");var line="";var offset=0f
  for(w in words){val next=if(line.isEmpty())w else line+" "+w;if(p.measureText(next)>width&&line.isNotEmpty()){c.drawText(line,x,y+offset,p);offset+=12f;line=w}else line=next}
  if(line.isNotEmpty())c.drawText(line,x,y+offset,p)
 }
}
