from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mysqldb import MySQL
from datetime import datetime
import MySQLdb.cursors

app = Flask(__name__)
app.secret_key = 'your_secret_key'
login_manager = LoginManager(app)
login_manager.login_view = 'login'

app = Flask(__name__)
app.secret_key = 'your_secret_key'
login_manager = LoginManager(app)
login_manager.login_view = 'login'



# MySQL 配置
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'  # 預設 XAMPP MySQL 的用戶名是 root
app.config['MYSQL_PASSWORD'] = ''  # 預設 XAMPP 沒有密碼
app.config['MYSQL_DB'] = 'shop_db'  # 你在 phpMyAdmin 中創建的資料庫名稱

mysql = MySQL(app)

# 首頁：顯示商品清單
@app.route('/')
def index():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM products')
    products = cursor.fetchall()
    return render_template('index.html', products=products)

# 將商品加入購物車
@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    quantity = int(request.form['quantity'])
    if 'cart' not in session:
        session['cart'] = {}
    cart = session['cart']

    if str(product_id) in cart:
        cart[str(product_id)] += quantity
    else:
        cart[str(product_id)] = quantity

    session['cart'] = cart
    return redirect(url_for('view_cart'))

# 顯示購物車內容
@app.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    if not cart:
        return render_template('cart.html', cart={}, products=[])

    product_ids = ','.join(cart.keys())
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(f'SELECT * FROM products WHERE product_id IN ({product_ids})')
    products = cursor.fetchall()
    return render_template('cart.html', cart=cart, products=products)

# 移除購物車中的商品
@app.route('/remove_from_cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    if str(product_id) in cart:
        del cart[str(product_id)]
    session['cart'] = cart
    return redirect(url_for('view_cart'))

# 結帳路由
@app.route('/checkout', methods=['POST'])
def checkout():
    cart = session.get('cart', {})
    if not cart:
        return redirect(url_for('view_cart'))  # 如果購物車為空，跳轉回購物車頁面

    # 計算購物車的總金額
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    total_amount = 0
    product_ids = ','.join(cart.keys())
    cursor.execute(f'SELECT * FROM products WHERE product_id IN ({product_ids})')
    products = cursor.fetchall()

    for product in products:
        product_id = str(product['product_id'])
        quantity = cart[product_id]
        total_amount += product['price'] * quantity

    # 插入訂單數據到 orders 表
    user_id = current_user.id
    cursor.execute('INSERT INTO orders (user_id, total_amount) VALUES (%s, %s)', (user_id, total_amount))
    mysql.connection.commit()
    order_id = cursor.lastrowid  # 獲取剛插入的訂單 ID

    # 插入每個商品到 order_items 表
    for product in products:
        product_id = product['product_id']
        quantity = cart[str(product_id)]
        price = product['price']
        cursor.execute(
            'INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (%s, %s, %s, %s)',
            (order_id, product_id, quantity, price)
        )

    mysql.connection.commit()
    cursor.close()

    # 清空購物車
    session.pop('cart', None)

    return render_template('checkout_success.html', order_id=order_id, total_amount=total_amount)

# 假設有個全局使用者類
class User(UserMixin):
    def __init__(self, user_id, username, role):
        self.id = user_id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
    user_data = cursor.fetchone()
    cursor.close()
    if user_data:
        return User(user_data['user_id'], user_data['username'], user_data['role'])
    return None

# 登入路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # 商家帳號硬編碼檢查
        if username == '11021' and password == '11021':
            login_user(User(0, 'seller', 'seller'))
            return redirect(url_for('seller_dashboard'))

        # 消費者帳號檢查
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()
        cursor.close()

        if user and check_password_hash(user['password'], password):
            login_user(User(user['user_id'], user['username'], user['role']))
            if user['role'] == 'buyer':
                return redirect(url_for('buyer_home'))
            elif user['role'] == 'seller':
                return redirect(url_for('seller_dashboard'))
        else:
            flash('Invalid credentials')

    return render_template('login.html')

# 註冊路由
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']  # 'buyer' or 'seller'

        hashed_password = generate_password_hash(password)

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('INSERT INTO users (username, password, role) VALUES (%s, %s, %s)', (username, hashed_password, role))
        mysql.connection.commit()
        cursor.close()

        return redirect(url_for('login'))

    return render_template('register.html')

# 買家首頁
@app.route('/buyer/home')
@login_required
def buyer_home():
    if current_user.role != 'buyer':
        return redirect(url_for('login'))
    return render_template('buyer_home.html')

# 商家儀表板
@app.route('/seller/dashboard')
@login_required
def seller_dashboard():
    if current_user.role != 'seller':
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('''
        SELECT orders.order_id, orders.total_amount, orders.order_date, 
               GROUP_CONCAT(products.name, ' x ', order_items.quantity SEPARATOR ', ') AS items
        FROM orders 
        JOIN order_items ON orders.order_id = order_items.order_id
        JOIN products ON order_items.product_id = products.product_id
        GROUP BY orders.order_id
    ''')
    orders = cursor.fetchall()
    cursor.close()

    return render_template('seller_dashboard.html', orders=orders)

if __name__ == '__main__':
    app.run(debug=True)
